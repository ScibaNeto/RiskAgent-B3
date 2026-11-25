"""VERSAO ANTERIOR da Fase 2; preservada para referencia.

Para novas execucoes da Fase 2.1, use phase2_risk_engine_v2.py.

RiskAgent B3 - Fase 2: Expected Shortfall, backtests e risco de carteira.

Uso (a partir da raiz do repositorio):
    py -m pip install -r requirements.txt
    py .\\src\\phase2_risk_engine.py

O script preserva a Fase 1. Ele reutiliza data/raw/*.csv quando disponivel,
atualiza os precos com Yahoo Finance e grava novos arquivos em outputs/.
Projeto educacional; nao e recomendacao de investimento.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import xlogy

try:
    import yfinance as yf
except ImportError:  # mensagem mais clara na inicializacao
    yf = None

try:
    from arch import arch_model
except ImportError:
    arch_model = None


# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "outputs"

ASSETS = {
    "PETR4": "PETR4.SA",
    "VALE3": "VALE3.SA",
    "IBOV": "^BVSP",  # benchmark; nao entra como posicao na carteira
}
PORTFOLIO_WEIGHTS = {"PETR4": 0.50, "VALE3": 0.50}

START_DATE = "2010-01-01"
ALPHA = 0.01                 # VaR de 99%: cauda inferior de 1%
WINDOW = 1000                # janela historica de estimacao
MIN_TEST_OBS = 250           # minimo de observacoes fora da amostra
GARCH_REFIT_EVERY = 20       # reestima GJR-GARCH a cada 20 pregoes
EWMA_LAMBDA = 0.94

LOG = logging.getLogger("riskagent.phase2")


@dataclass
class ForecastSet:
    """Previsoes de VaR e ES para um ativo/modelo."""
    var: pd.Series
    es: pd.Series


# ---------------------------------------------------------------------------
# UTILITARIOS DE DATA E CACHE
# ---------------------------------------------------------------------------
def _normalise_price_series(series: pd.Series, name: str) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    idx = pd.to_datetime(series.index, errors="coerce")
    valid = ~pd.isna(idx)
    series = series.loc[valid]
    idx = idx[valid]
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    series.index = idx.normalize()
    series = series[~series.index.duplicated(keep="last")].sort_index()
    series = series[series > 0]
    series.name = name
    return series


def _read_price_cache(path: Path, name: str) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype=float, name=name)
    try:
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        if frame.empty:
            return pd.Series(dtype=float, name=name)
        preferred = next((c for c in ("Close", "Adj Close", "price", name) if c in frame.columns), frame.columns[0])
        return _normalise_price_series(frame[preferred], name)
    except Exception as exc:
        LOG.warning("Nao foi possivel ler o cache %s: %s", path, exc)
        return pd.Series(dtype=float, name=name)


def _download_yahoo(ticker: str, name: str) -> pd.Series:
    if yf is None:
        raise RuntimeError("Pacote yfinance ausente. Instale com: py -m pip install yfinance")

    # auto_adjust=True faz o campo Close representar o preco ajustado.
    data = yf.download(
        ticker,
        start=START_DATE,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if data is None or data.empty:
        # Segunda tentativa usando a interface Ticker.history.
        data = yf.Ticker(ticker).history(start=START_DATE, auto_adjust=True)
    if data is None or data.empty:
        raise RuntimeError(f"Yahoo Finance nao retornou precos para {ticker}.")
    if isinstance(data.columns, pd.MultiIndex):
        has_close = "Close" in data.columns.get_level_values(0)
    else:
        has_close = "Close" in data.columns
    if not has_close:
        raise RuntimeError(f"Yahoo Finance nao retornou a coluna Close para {ticker}.")

    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        if ticker in close.columns:
            close = close[ticker]
        else:
            close = close.iloc[:, 0]
    return _normalise_price_series(close, name)


def load_prices(name: str, ticker: str) -> pd.Series:
    """Carrega cache local e tenta atualiza-lo com dados do Yahoo Finance."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DATA_DIR / f"{name}.csv"
    cached = _read_price_cache(cache_path, name)
    downloaded = pd.Series(dtype=float, name=name)

    try:
        downloaded = _download_yahoo(ticker, name)
        LOG.info("%s: %s precos recebidos do Yahoo Finance.", name, len(downloaded))
    except Exception as exc:
        if cached.empty:
            raise RuntimeError(
                f"Falha ao obter {name} ({ticker}) e nao existe cache local. "
                f"Verifique a internet e tente novamente. Detalhe: {exc}"
            ) from exc
        LOG.warning("%s: Yahoo Finance indisponivel; usando cache local (%s).", name, exc)

    if cached.empty:
        prices = downloaded
    elif downloaded.empty:
        prices = cached
    else:
        prices = pd.concat([cached, downloaded]).groupby(level=0).last().sort_index()
        prices.name = name

    minimum = WINDOW + MIN_TEST_OBS + 1
    if len(prices) < minimum:
        raise RuntimeError(
            f"Dados insuficientes para {name}: {len(prices)} precos; minimo recomendado: {minimum}."
        )

    prices.index.name = "Date"
    prices.to_frame("Close").to_csv(cache_path)
    return prices


def prices_to_returns(prices: pd.Series) -> pd.Series:
    """Retornos logaritmicos diarios em porcentagem."""
    returns = (100.0 * np.log(prices / prices.shift(1))).replace([np.inf, -np.inf], np.nan).dropna()
    returns.name = prices.name
    return returns


# ---------------------------------------------------------------------------
# MODELOS DE PREVISAO: CADA PREVISAO USA SOMENTE INFORMACAO PASSADA
# ---------------------------------------------------------------------------
def historical_var_es(returns: pd.Series) -> ForecastSet:
    values = returns.to_numpy(dtype=float)
    var = np.full(len(values), np.nan)
    es = np.full(len(values), np.nan)
    for t in range(WINDOW, len(values)):
        sample = values[t - WINDOW:t]
        q = float(np.quantile(sample, ALPHA))
        tail = sample[sample <= q]
        var[t] = q
        es[t] = float(tail.mean()) if tail.size else q
    return ForecastSet(
        pd.Series(var, index=returns.index, name="VaR"),
        pd.Series(es, index=returns.index, name="ES"),
    )


def ewma_var_es(returns: pd.Series) -> ForecastSet:
    # Variancia no instante t usa dados ate t-1 (shift(1)).
    variance = returns.pow(2).ewm(alpha=1.0 - EWMA_LAMBDA, adjust=False).mean().shift(1)
    sigma = np.sqrt(variance.clip(lower=0.0))
    z = float(stats.norm.ppf(ALPHA))
    var = z * sigma
    es = -(stats.norm.pdf(z) / ALPHA) * sigma
    var.iloc[:WINDOW] = np.nan
    es.iloc[:WINDOW] = np.nan
    return ForecastSet(var.rename("VaR"), es.rename("ES"))


def _standard_t_var_es(alpha: float, degrees_freedom: float) -> tuple[float, float]:
    """Quantil e ES da t-Student padronizada para variancia unitaria."""
    nu = float(degrees_freedom)
    if not np.isfinite(nu) or nu <= 2.0:
        raise ValueError(f"Graus de liberdade invalidos para t-Student: {nu}")
    scale = np.sqrt((nu - 2.0) / nu)
    q_raw = float(stats.t.ppf(alpha, df=nu))
    var_z = scale * q_raw
    density = float(stats.t.pdf(q_raw, df=nu))
    es_raw = -((nu + q_raw * q_raw) / (nu - 1.0)) * density / alpha
    es_z = scale * es_raw
    return var_z, es_z


def gjr_garch_t_var_es(returns: pd.Series, asset: str) -> tuple[ForecastSet, list[dict[str, Any]]]:
    """GJR-GARCH(1,1)-t com reestimativa periodica e previsao sem olhar o futuro.

    Os parametros sao estimados na janela anterior a cada bloco. Dentro do bloco,
    os parametros ficam fixos, mas a volatilidade condicional e atualizada com os
    retornos que ja teriam sido observados ate cada data de previsao.
    """
    if arch_model is None:
        raise RuntimeError("Pacote arch ausente. Instale com: py -m pip install arch")

    values = returns.to_numpy(dtype=float)
    var_values = np.full(len(values), np.nan)
    es_values = np.full(len(values), np.nan)
    diagnostics: list[dict[str, Any]] = []
    spec = {"mean": "Zero", "vol": "GARCH", "p": 1, "o": 1, "q": 1, "dist": "t", "rescale": False}

    for start in range(WINDOW, len(values), GARCH_REFIT_EVERY):
        stop = min(start + GARCH_REFIT_EVERY, len(values))
        fit_sample = returns.iloc[start - WINDOW:start]
        fit_date_start = str(fit_sample.index[0].date())
        fit_date_end = str(fit_sample.index[-1].date())
        row: dict[str, Any] = {
            "asset": asset,
            "fit_start": fit_date_start,
            "fit_end": fit_date_end,
            "forecast_start": str(returns.index[start].date()),
            "forecast_end": str(returns.index[stop - 1].date()),
            "convergence_flag": np.nan,
            "nu": np.nan,
            "status": "failed",
            "message": "",
        }
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                fitted = arch_model(fit_sample, **spec).fit(disp="off", show_warning=False)
            row["convergence_flag"] = int(getattr(fitted, "convergence_flag", 0))
            nu = float(fitted.params.get("nu", np.nan))
            row["nu"] = nu
            if row["convergence_flag"] != 0:
                raise RuntimeError(f"Otimizador nao convergiu (flag={row['convergence_flag']}).")
            q_z, es_z = _standard_t_var_es(ALPHA, nu)
            params = fitted.params

            # Para cada dia t, filtra apenas retornos anteriores a t.
            for t in range(start, stop):
                known_returns = returns.iloc[:t]
                fixed = arch_model(known_returns, **spec).fix(params)
                sigma_t = float(fixed.conditional_volatility.iloc[-1])
                if not np.isfinite(sigma_t) or sigma_t <= 0:
                    raise RuntimeError("Volatilidade condicional invalida.")
                var_values[t] = q_z * sigma_t
                es_values[t] = es_z * sigma_t

            row["status"] = "ok"
            row["message"] = " | ".join(str(w.message) for w in caught[-2:])
        except Exception as exc:
            row["message"] = str(exc)[:500]
            LOG.warning("GJR-GARCH falhou em %s, bloco %s: %s", asset, fit_date_end, exc)
        diagnostics.append(row)

    return (
        ForecastSet(
            pd.Series(var_values, index=returns.index, name="VaR"),
            pd.Series(es_values, index=returns.index, name="ES"),
        ),
        diagnostics,
    )


# ---------------------------------------------------------------------------
# BACKTESTS: KUPIEC, CHRISTOFFERSEN E COBERTURA CONDICIONAL
# ---------------------------------------------------------------------------
def kupiec_unconditional_coverage(violations: np.ndarray, alpha: float = ALPHA) -> tuple[float, float]:
    """LR de Kupiec (UC): H0 de taxa de violacoes igual a alpha."""
    v = np.asarray(violations, dtype=int)
    n = int(v.size)
    x = int(v.sum())
    if n == 0:
        return np.nan, np.nan
    p_hat = x / n
    ll_null = float(xlogy(x, alpha) + xlogy(n - x, 1.0 - alpha))
    ll_alt = float(xlogy(x, p_hat) + xlogy(n - x, 1.0 - p_hat))
    lr = max(0.0, 2.0 * (ll_alt - ll_null))
    return lr, float(stats.chi2.sf(lr, df=1))


def christoffersen_independence(violations: np.ndarray) -> tuple[float, float, dict[str, int]]:
    """Teste de independencia de Christoffersen baseado em transicoes 0/1."""
    v = np.asarray(violations, dtype=int)
    if v.size < 2:
        return np.nan, np.nan, {"n00": 0, "n01": 0, "n10": 0, "n11": 0}
    previous, current = v[:-1], v[1:]
    n00 = int(np.sum((previous == 0) & (current == 0)))
    n01 = int(np.sum((previous == 0) & (current == 1)))
    n10 = int(np.sum((previous == 1) & (current == 0)))
    n11 = int(np.sum((previous == 1) & (current == 1)))

    total = n00 + n01 + n10 + n11
    p = (n01 + n11) / total if total else 0.0
    denom01 = n00 + n01
    denom11 = n10 + n11
    p01 = n01 / denom01 if denom01 else 0.0
    p11 = n11 / denom11 if denom11 else 0.0

    ll_null = float(xlogy(n01 + n11, p) + xlogy(n00 + n10, 1.0 - p))
    ll_alt = float(
        xlogy(n01, p01) + xlogy(n00, 1.0 - p01)
        + xlogy(n11, p11) + xlogy(n10, 1.0 - p11)
    )
    lr = max(0.0, 2.0 * (ll_alt - ll_null))
    counts = {"n00": n00, "n01": n01, "n10": n10, "n11": n11}
    return lr, float(stats.chi2.sf(lr, df=1)), counts


def evaluate_forecasts(asset: str, model: str, returns: pd.Series, forecast: ForecastSet) -> dict[str, Any]:
    frame = pd.concat([returns.rename("return_pct"), forecast.var.rename("var_pct"), forecast.es.rename("es_pct")], axis=1).dropna()
    if len(frame) < MIN_TEST_OBS:
        raise RuntimeError(
            f"Amostra fora da amostra insuficiente para {asset}/{model}: {len(frame)} observacoes; "
            f"minimo: {MIN_TEST_OBS}."
        )
    violations = (frame["return_pct"] < frame["var_pct"]).to_numpy(dtype=int)
    lr_uc, p_uc = kupiec_unconditional_coverage(violations)
    lr_ind, p_ind, transitions = christoffersen_independence(violations)
    lr_cc = lr_uc + lr_ind if np.isfinite(lr_uc) and np.isfinite(lr_ind) else np.nan
    p_cc = float(stats.chi2.sf(lr_cc, df=2)) if np.isfinite(lr_cc) else np.nan

    breach_returns = frame.loc[violations == 1, "return_pct"]
    breach_es = frame.loc[violations == 1, "es_pct"]
    avg_realised_tail = float(breach_returns.mean()) if not breach_returns.empty else np.nan
    avg_forecast_es_on_breach = float(breach_es.mean()) if not breach_es.empty else np.nan

    return {
        "asset": asset,
        "model": model,
        "n_obs": int(len(frame)),
        "violations": int(violations.sum()),
        "expected_violations": float(len(frame) * ALPHA),
        "violation_rate_pct": float(100.0 * violations.mean()),
        "avg_var_pct": float(frame["var_pct"].mean()),
        "avg_es_pct": float(frame["es_pct"].mean()),
        "avg_realised_return_on_violations_pct": avg_realised_tail,
        "avg_forecast_es_on_violations_pct": avg_forecast_es_on_breach,
        "kupiec_lr_uc": float(lr_uc),
        "kupiec_p_value": float(p_uc),
        "christoffersen_lr_ind": float(lr_ind),
        "christoffersen_p_value": float(p_ind),
        "conditional_coverage_lr": float(lr_cc),
        "conditional_coverage_p_value": float(p_cc),
        **transitions,
        "kupiec_result_5pct": "nao_rejeita" if p_uc >= 0.05 else "rejeita",
        "independence_result_5pct": "nao_rejeita" if p_ind >= 0.05 else "rejeita",
        "conditional_coverage_result_5pct": "nao_rejeita" if p_cc >= 0.05 else "rejeita",
    }


# ---------------------------------------------------------------------------
# EXPORTACAO, GRAFICOS E RELATORIO
# ---------------------------------------------------------------------------
def build_forecast_table(asset: str, returns: pd.Series) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    forecast_sets: dict[str, ForecastSet] = {
        "Simulacao historica": historical_var_es(returns),
        "EWMA normal": ewma_var_es(returns),
    }
    garch_forecast, diagnostics = gjr_garch_t_var_es(returns, asset)
    forecast_sets["GJR-GARCH t"] = garch_forecast

    rows = []
    for model_name, result in forecast_sets.items():
        frame = pd.DataFrame({
            "date": returns.index,
            "asset": asset,
            "model": model_name,
            "return_pct": returns.to_numpy(),
            "var_pct": result.var.to_numpy(),
            "es_pct": result.es.to_numpy(),
        })
        rows.append(frame)
    return pd.concat(rows, ignore_index=True), diagnostics


def save_portfolio_weights() -> pd.DataFrame:
    total = sum(PORTFOLIO_WEIGHTS.values())
    if not np.isclose(total, 1.0, atol=1e-8):
        raise ValueError(f"Os pesos da carteira precisam somar 1.0; soma atual: {total:.6f}")
    if any(weight < 0 for weight in PORTFOLIO_WEIGHTS.values()):
        raise ValueError("Esta versao nao permite pesos negativos/posicoes vendidas a descoberto.")
    rows = [{"asset": asset, "weight": weight, "role": "posicao_da_carteira"} for asset, weight in PORTFOLIO_WEIGHTS.items()]
    rows.append({"asset": "IBOV", "weight": np.nan, "role": "benchmark_separado"})
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT_DIR / "phase2_portfolio_weights.csv", index=False)
    return frame


def plot_portfolio(portfolio_forecasts: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = portfolio_forecasts.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date")

    # VaR e retornos realizados.
    fig, ax = plt.subplots(figsize=(13, 6))
    base = data[data["model"] == "GJR-GARCH t"].dropna(subset=["var_pct"])
    ax.plot(base["date"], base["return_pct"], color="0.65", linewidth=0.7, label="Retorno da carteira")
    ax.plot(base["date"], base["var_pct"], linewidth=1.2, label="VaR 99% — GJR-GARCH-t")
    breached = base[base["return_pct"] < base["var_pct"]]
    ax.scatter(breached["date"], breached["return_pct"], marker="x", s=24, label="Violacoes do VaR")
    ax.set_title("Carteira PETR4/VALE3 — retornos e VaR 99%")
    ax.set_ylabel("Retorno diario (%)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "phase2_portfolio_var.png", dpi=150)
    plt.close(fig)

    # Comparacao ES entre os tres metodos.
    fig, ax = plt.subplots(figsize=(13, 6))
    for model_name, group in data.groupby("model"):
        group = group.dropna(subset=["es_pct"])
        ax.plot(group["date"], group["es_pct"], linewidth=1.1, label=model_name)
    ax.set_title("Carteira PETR4/VALE3 — Expected Shortfall 99%")
    ax.set_ylabel("ES diario (%) — valores negativos")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "phase2_portfolio_es.png", dpi=150)
    plt.close(fig)

    # Frequencia de violacoes por modelo para a carteira.
    fig, ax = plt.subplots(figsize=(9, 5))
    labels, rates = [], []
    for model_name, group in data.groupby("model"):
        group = group.dropna(subset=["return_pct", "var_pct"])
        if not group.empty:
            labels.append(model_name)
            rates.append(100.0 * (group["return_pct"] < group["var_pct"]).mean())
    ax.bar(labels, rates)
    ax.axhline(100.0 * ALPHA, linestyle="--", linewidth=1.2, label="Taxa esperada: 1%")
    ax.set_title("Carteira — taxa observada de violacoes do VaR")
    ax.set_ylabel("Violacoes (%)")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "phase2_backtest_exceptions.png", dpi=150)
    plt.close(fig)


def write_report(metrics: pd.DataFrame, diagnostics: pd.DataFrame, prices_info: dict[str, int]) -> None:
    report_path = OUTPUT_DIR / "phase2_report.md"
    lines = [
        "# RiskAgent B3 — Relatorio da Fase 2",
        "",
        "Projeto educacional. Este relatorio nao e recomendacao de investimento.",
        "",
        f"Execucao UTC: {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S')}",
        f"Nivel de cauda: {ALPHA:.1%} | VaR: {(1-ALPHA):.0%} | Janela: {WINDOW} pregoes",
        "",
        "## Dados utilizados",
        "",
    ]
    for asset, count in prices_info.items():
        lines.append(f"- {asset}: {count} precos disponiveis")
    lines += [
        "",
        "## Carteira demonstrativa",
        "",
        "- PETR4: 50%",
        "- VALE3: 50%",
        "- Ibovespa: benchmark separado; nao e uma posicao da carteira.",
        "- A serie de carteira usa pesos constantes aplicados diariamente (rebalanceamento diario implicito).",
        "",
        "## Como interpretar os testes",
        "",
        "- Kupiec (UC): avalia se a frequencia de violacoes e compativel com o nivel de cauda de 1%.",
        "- Christoffersen (IND): avalia se as violacoes sao independentes ao longo do tempo.",
        "- Cobertura condicional (CC): combina frequencia e independencia.",
        "- p-valor >= 0,05 significa que o teste nao rejeitou a hipotese nula; nao prova que o modelo seja perfeito.",
        "- Um teste de VaR aprovado nao garante que o ES esteja correto; o ES tambem exige avaliacao propria.",
        "",
        "## Resultados por ativo/modelo",
        "",
    ]
    if metrics.empty:
        lines.append("Nenhuma combinacao teve amostra suficiente para avaliacao.")
    else:
        cols = ["asset", "model", "n_obs", "violations", "violation_rate_pct", "avg_var_pct", "avg_es_pct", "kupiec_p_value", "christoffersen_p_value", "conditional_coverage_p_value"]
        view = metrics[cols].copy()
        lines.append("```text")
        lines.append(view.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
        lines.append("```")
    if diagnostics is not None and not diagnostics.empty:
        lines += ["", "## Diagnostico das estimacoes GJR-GARCH-t", ""]
        status_counts = diagnostics.groupby(["asset", "status"]).size().unstack(fill_value=0)
        lines.append("```text")
        lines.append(status_counts.to_string())
        lines.append("```")
    lines += [
        "",
        "## Arquivos",
        "",
        "- `phase2_metrics.csv`: metricas e testes estatisticos.",
        "- `phase2_forecasts.csv`: previsoes diarias de VaR e ES.",
        "- `phase2_garch_diagnostics.csv`: convergencia das estimacoes GJR-GARCH.",
        "- `phase2_portfolio_weights.csv`: pesos usados na carteira demonstrativa.",
        "- `phase2_portfolio_var.png`, `phase2_portfolio_es.png` e `phase2_backtest_exceptions.png`: graficos.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if arch_model is None:
        raise SystemExit("Dependencia ausente: arch. Execute: py -m pip install arch")
    if yf is None and not all((DATA_DIR / f"{name}.csv").exists() for name in ASSETS):
        raise SystemExit("Dependencia ausente: yfinance. Execute: py -m pip install yfinance")

    price_series: dict[str, pd.Series] = {}
    returns: dict[str, pd.Series] = {}
    for asset, ticker in ASSETS.items():
        LOG.info("Carregando dados de %s (%s)...", asset, ticker)
        price_series[asset] = load_prices(asset, ticker)
        returns[asset] = prices_to_returns(price_series[asset])
        LOG.info("%s: %s retornos diarios.", asset, len(returns[asset]))

    # Carteira 50/50 de PETR4 e VALE3, com datas comuns.
    portfolio_components = pd.concat(
        [returns[name].rename(name) for name in PORTFOLIO_WEIGHTS], axis=1, join="inner"
    ).dropna()
    weights = pd.Series(PORTFOLIO_WEIGHTS, dtype=float)
    portfolio_returns = portfolio_components.mul(weights, axis=1).sum(axis=1)
    portfolio_returns.name = "PORTFOLIO_50_50"
    returns[portfolio_returns.name] = portfolio_returns

    save_portfolio_weights()

    forecast_tables: list[pd.DataFrame] = []
    all_diagnostics: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    for asset, series in returns.items():
        LOG.info("Calculando previsoes para %s...", asset)
        table, diagnostics = build_forecast_table(asset, series)
        forecast_tables.append(table)
        all_diagnostics.extend(diagnostics)

    forecasts = pd.concat(forecast_tables, ignore_index=True)
    forecasts.to_csv(OUTPUT_DIR / "phase2_forecasts.csv", index=False, float_format="%.8f")

    for (asset, model_name), group in forecasts.groupby(["asset", "model"]):
        group = group.sort_values("date")
        r = pd.Series(group["return_pct"].to_numpy(), index=pd.to_datetime(group["date"]))
        var = pd.Series(group["var_pct"].to_numpy(), index=r.index)
        es = pd.Series(group["es_pct"].to_numpy(), index=r.index)
        try:
            metric_rows.append(evaluate_forecasts(asset, model_name, r, ForecastSet(var, es)))
        except RuntimeError as exc:
            LOG.warning("Avaliacao ignorada para %s/%s: %s", asset, model_name, exc)

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(OUTPUT_DIR / "phase2_metrics.csv", index=False, float_format="%.8f")
    diagnostics_frame = pd.DataFrame(all_diagnostics)
    diagnostics_frame.to_csv(OUTPUT_DIR / "phase2_garch_diagnostics.csv", index=False)

    portfolio_table = forecasts[forecasts["asset"] == "PORTFOLIO_50_50"].copy()
    plot_portfolio(portfolio_table)
    write_report(metrics, diagnostics_frame, {name: len(values) for name, values in price_series.items()})

    print("\nFASE 2 CONCLUIDA")
    print(f"Resultados salvos em: {OUTPUT_DIR}")
    print("Arquivos principais:")
    for filename in [
        "phase2_metrics.csv",
        "phase2_forecasts.csv",
        "phase2_garch_diagnostics.csv",
        "phase2_portfolio_weights.csv",
        "phase2_report.md",
        "phase2_portfolio_var.png",
        "phase2_portfolio_es.png",
        "phase2_backtest_exceptions.png",
    ]:
        print(f" - {filename}")
    if not metrics.empty:
        display_cols = ["asset", "model", "n_obs", "violations", "violation_rate_pct", "kupiec_p_value", "christoffersen_p_value", "conditional_coverage_p_value"]
        print("\nResumo dos backtests:")
        print(metrics[display_cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    successful = int((diagnostics_frame["status"] == "ok").sum()) if not diagnostics_frame.empty else 0
    total = len(diagnostics_frame)
    print(f"\nEstimativas GJR-GARCH convergentes: {successful}/{total}")


if __name__ == "__main__":
    main()
