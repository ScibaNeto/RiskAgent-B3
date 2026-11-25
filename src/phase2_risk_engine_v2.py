"""RiskAgent B3 - Fase 2.1 (implementacao oficial): ES, backtests e carteira.

Uso (a partir da raiz do repositorio):
    py -m pip install -r requirements.txt
    py .\\src\\phase2_risk_engine_v2.py

O script preserva a Fase 1. Ele reutiliza data/raw/*.csv quando disponivel,
atualiza os precos com Yahoo Finance e grava novos arquivos em outputs/.
Projeto educacional; nao e recomendacao de investimento.
"""
from __future__ import annotations

import logging
import argparse
import json
import warnings
import unicodedata
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

if __package__:
    from .risk_extensions import write_extensions
    from . import market_data
    from .b3_sessions import daily_log_returns, session_prices
    from .data_manifest import write_data_manifest
else:
    from risk_extensions import write_extensions
    import market_data
    from b3_sessions import daily_log_returns, session_prices
    from data_manifest import write_data_manifest

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
OUTPUT_ROOT = ROOT / "outputs" / "phase2_1"
OUTPUT_DIR = OUTPUT_ROOT

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
MIN_PERIOD_OBS = 250         # minimo para backtests por periodo
GARCH_REFIT_EVERY = 20       # reestima GJR-GARCH a cada 20 pregoes
EWMA_LAMBDA = 0.94
CACHE_OVERLAP_DAYS = 5
MIN_TOTAL_RETURNS = WINDOW + MIN_TEST_OBS

LOG = logging.getLogger("riskagent.phase2")
DATA_SOURCES: dict[str, str] = {}


@dataclass
class ForecastSet:
    """Previsoes de VaR e ES para um ativo/modelo."""
    var: pd.Series
    es: pd.Series


# ---------------------------------------------------------------------------
# UTILITARIOS DE DATA E CACHE
# ---------------------------------------------------------------------------
def _normalise_price_series(series: pd.Series, name: str) -> pd.Series:
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    return market_data.clean_prices(series, name, today)[0]


def _download_yahoo(ticker: str, name: str, start_date: str = START_DATE) -> pd.Series:
    if yf is None:
        raise RuntimeError("Pacote yfinance ausente. Instale com: py -m pip install yfinance")

    # auto_adjust=True faz o campo Close representar o preco ajustado.
    data = yf.download(
        ticker,
        start=start_date,
        auto_adjust=True,
        progress=False,
        threads=False,
        timeout=15,
    )
    if data is None or data.empty:
        # Segunda tentativa usando a interface Ticker.history.
        data = yf.Ticker(ticker).history(start=start_date, auto_adjust=True, timeout=15)
    if data is None or data.empty:
        raise RuntimeError(f"Yahoo Finance nao retornou precos para {ticker}.")
    if isinstance(data.columns, pd.MultiIndex):
        has_close = "Close" in data.columns.get_level_values(0)
    else:
        has_close = "Close" in data.columns
    if not has_close:
        return data  # preserva a resposta inválida para quarentena

    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        if ticker in close.columns:
            close = close[ticker]
        else:
            close = close.iloc[:, 0]
    return close


def _validate_return_sample(prices: pd.Series, name: str) -> pd.Series:
    returns = prices_to_returns(prices)
    if len(returns) < MIN_TOTAL_RETURNS:
        raise RuntimeError(
            f"Amostra insuficiente para {name}: {len(returns)} retornos validos; "
            f"minimo exigido: {MIN_TOTAL_RETURNS}."
        )
    return returns


def _load_input(name: str, ticker: str, strict_cache: bool = False, **options):
    result = market_data.ingest(
        name, cache_path=DATA_DIR / f"{name}.csv", start=START_DATE,
        minimum=MIN_TOTAL_RETURNS, overlap_days=CACHE_OVERLAP_DAYS,
        symbol=ticker, fetch=lambda start: _download_yahoo(ticker, name, start_date=start),
        attempts=3, strict=strict_cache, **options,
    )
    DATA_SOURCES[name] = result.record["source_mode"]
    return result


def load_prices(name: str, ticker: str, strict_cache: bool = False, **options) -> pd.Series:
    return _load_input(name, ticker, strict_cache, **options).prices


def prices_to_returns(prices: pd.Series) -> pd.Series:
    return daily_log_returns(prices)


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


def _fixed_garch_block_sigma(
    returns: pd.Series,
    params: pd.Series,
    spec: dict[str, Any],
    start: int,
    stop: int,
) -> np.ndarray:
    """Filtra volatilidades de start:stop usando a janela passada e o bloco atual.

    `conditional_volatility` na primeira linha após a janela estima h_t usando
    observacoes somente ate t-1. Incluir o bloco permite atualizar a recursao
    para os dias seguintes sem reajustar parametros nem usar o retorno do proprio dia.
    """
    known_and_block = returns.iloc[start - WINDOW:stop]
    fixed = arch_model(known_and_block, **spec).fix(params)
    sigma = fixed.conditional_volatility.iloc[WINDOW:].to_numpy(dtype=float)
    expected = stop - start
    if len(sigma) != expected:
        raise RuntimeError(f"Bloco GARCH retornou {len(sigma)} volatilidades; esperado: {expected}.")
    if not np.isfinite(sigma).all() or (sigma <= 0).any():
        raise RuntimeError("Volatilidade condicional invalida no bloco GARCH.")
    return sigma


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
            "optimization_method": "SLSQP (arch default)",
            "iterations": np.nan,
            "log_likelihood": np.nan,
            "nu": np.nan,
            "parameters_json": "",
            "status": "failed",
            "message": "",
        }
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                fitted = arch_model(fit_sample, **spec).fit(disp="off", show_warning=False)
            convergence_flag = getattr(fitted, "convergence_flag", None)
            if convergence_flag is None:
                raise RuntimeError("Resultado do ajuste sem indicador de convergencia.")
            row["convergence_flag"] = int(convergence_flag)
            optimization_result = getattr(fitted, "optimization_result", None)
            row["iterations"] = getattr(optimization_result, "nit", np.nan)
            row["log_likelihood"] = float(fitted.loglikelihood)
            nu = float(fitted.params.get("nu", np.nan))
            row["nu"] = nu
            if row["convergence_flag"] != 0:
                raise RuntimeError(f"Otimizador nao convergiu (flag={row['convergence_flag']}).")
            q_z, es_z = _standard_t_var_es(ALPHA, nu)
            params = fitted.params
            row["parameters_json"] = json.dumps({key: float(value) for key, value in params.items()}, sort_keys=True)
            sigma = _fixed_garch_block_sigma(returns, params, spec, start, stop)
            var_values[start:stop] = q_z * sigma
            es_values[start:stop] = es_z * sigma

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
    return _kupiec_from_counts(int(v.size), int(v.sum()), alpha)


def _kupiec_from_counts(n: int, x: int, alpha: float) -> tuple[float, float]:
    if n == 0:
        return np.nan, np.nan
    p_hat = x / n
    ll_null = float(xlogy(x, alpha) + xlogy(n - x, 1.0 - alpha))
    ll_alt = float(xlogy(x, p_hat) + xlogy(n - x, 1.0 - p_hat))
    lr = max(0.0, 2.0 * (ll_alt - ll_null))
    return lr, float(stats.chi2.sf(lr, df=1))


def adjust_pvalues(pvalues: pd.Series, method: str) -> pd.Series:
    """Ajusta p-valores sem mudar os valores originais; NaN permanece NaN."""
    method = method.lower()
    if method not in {"holm", "bh"}:
        raise ValueError("method deve ser 'holm' ou 'bh'.")
    values = pd.to_numeric(pvalues, errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(values)
    if np.any((values[valid] < 0.0) | (values[valid] > 1.0)):
        raise ValueError("p-valores finitos devem estar entre 0 e 1.")
    adjusted = np.full(values.size, np.nan, dtype=float)
    p = values[valid]
    m = p.size
    if m:
        order = np.argsort(p, kind="mergesort")
        sorted_p = p[order]
        if method == "holm":
            raw = (m - np.arange(m)) * sorted_p
            sorted_adj = np.minimum(1.0, np.maximum.accumulate(raw))
        else:
            raw = sorted_p * m / np.arange(1, m + 1)
            sorted_adj = np.minimum(1.0, np.minimum.accumulate(raw[::-1])[::-1])
        restored = np.empty(m, dtype=float)
        restored[order] = sorted_adj
        adjusted[valid] = restored
    return pd.Series(adjusted, index=pvalues.index, name=f"{pvalues.name}_{method}")


def add_adjusted_pvalues(frame: pd.DataFrame, pvalue_columns: list[str], method: str) -> pd.DataFrame:
    result = frame.copy()
    for column in pvalue_columns:
        if column in result:
            result[f"{column}_{method}"] = adjust_pvalues(result[column], method)
    return result


def christoffersen_independence(violations: np.ndarray) -> tuple[float, float, dict[str, int]]:
    """Conta transições entre posições vizinhas. Um NaN interrompe a sequência."""
    v = np.asarray(violations, dtype=float)
    if v.ndim != 1 or not np.all(np.isnan(v) | np.isin(v, [0, 1])):
        raise ValueError("Use indicadores de violação 0/1 ou NaN para um pregão ausente.")
    previous, current = v[:-1], v[1:]
    n00 = int(np.sum((previous == 0) & (current == 0)))
    n01 = int(np.sum((previous == 0) & (current == 1)))
    n10 = int(np.sum((previous == 1) & (current == 0)))
    n11 = int(np.sum((previous == 1) & (current == 1)))

    counts = {"n00": n00, "n01": n01, "n10": n10, "n11": n11}
    # A comparação assintótica exige dois estados de origem e de destino observados.
    if min(n00 + n01, n10 + n11, n00 + n10, n01 + n11) == 0:
        return np.nan, np.nan, counts
    p = (n01 + n11) / sum(counts.values())
    denom01 = n00 + n01
    denom11 = n10 + n11
    p01 = n01 / denom01
    p11 = n11 / denom11

    ll_null = float(xlogy(n01 + n11, p) + xlogy(n00 + n10, 1.0 - p))
    ll_alt = float(
        xlogy(n01, p01) + xlogy(n00, 1.0 - p01)
        + xlogy(n11, p11) + xlogy(n10, 1.0 - p11)
    )
    lr = max(0.0, 2.0 * (ll_alt - ll_null))
    return lr, float(stats.chi2.sf(lr, df=1)), counts


def fz0_es_score(returns: pd.Series, var: pd.Series, es: pd.Series, alpha: float = ALPHA) -> dict[str, float]:
    """Score FZ0 conjunto para VaR/ES, calculado na cauda de perdas.

    Converte retornos em perdas (loss=-return). Score menor e melhor.
    E uma regra de pontuacao comparativa; nao e um teste de hipotese/p-valor.
    """
    frame = pd.concat(
        [returns.rename("return_pct"), var.rename("var_pct"), es.rename("es_pct")], axis=1
    ).replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        return {"fz0_score_mean": np.nan, "fz0_score_median": np.nan, "fz0_obs": 0}

    loss = -frame["return_pct"].to_numpy(dtype=float)
    var_loss = -frame["var_pct"].to_numpy(dtype=float)
    es_loss = -frame["es_pct"].to_numpy(dtype=float)
    # ES de perdas deve ser positivo e nao inferior ao VaR de perdas.
    valid = np.isfinite(loss) & np.isfinite(var_loss) & np.isfinite(es_loss)
    valid &= (es_loss > 0.0) & (var_loss > 0.0) & (es_loss >= var_loss)
    if not np.any(valid):
        return {"fz0_score_mean": np.nan, "fz0_score_median": np.nan, "fz0_obs": 0}

    loss = loss[valid]
    var_loss = var_loss[valid]
    es_loss = es_loss[valid]
    exceedance = (loss > var_loss).astype(float)
    score = (
        exceedance * np.maximum(loss - var_loss, 0.0) / (alpha * es_loss)
        + var_loss / es_loss
        + np.log(es_loss)
        - 1.0
    )
    return {
        "fz0_score_mean": float(np.mean(score)),
        "fz0_score_median": float(np.median(score)),
        "fz0_obs": int(score.size),
    }


def _test_verdict(p_value: float) -> str:
    if not np.isfinite(p_value):
        return "indisponivel"
    return "nao_rejeita" if p_value >= 0.05 else "rejeita"


def evaluate_forecasts(
    asset: str,
    model: str,
    returns: pd.Series,
    forecast: ForecastSet,
    min_obs: int = MIN_TEST_OBS,
) -> dict[str, Any]:
    frame = pd.concat(
        [returns.rename("return_pct"), forecast.var.rename("var_pct"), forecast.es.rename("es_pct")],
        axis=1,
    ).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < min_obs:
        raise RuntimeError(
            f"Amostra insuficiente para {asset}/{model}: {len(frame)} observacoes; minimo: {min_obs}."
        )

    indicators = (frame["return_pct"] < frame["var_pct"]).astype(int)
    violations = indicators.to_numpy()
    lr_uc, p_uc = kupiec_unconditional_coverage(violations)
    if isinstance(indicators.index, pd.DatetimeIndex):
        indicators = indicators.sort_index()
        calendar_hits = session_prices(indicators)
        if not indicators.index.isin(calendar_hits.index).all():
            raise ValueError("O backtest diário contém datas fora do calendário BVMF.")
    else:
        calendar_hits = indicators
    lr_ind, p_ind, transitions = christoffersen_independence(calendar_hits.to_numpy())
    pair_count = sum(transitions.values())
    # A cobertura condicional usa os destinos das mesmas transições que a independência.
    lr_pair_uc, _ = _kupiec_from_counts(pair_count, transitions["n01"] + transitions["n11"], ALPHA)
    lr_cc = lr_pair_uc + lr_ind
    p_cc = float(stats.chi2.sf(lr_cc, df=2)) if np.isfinite(lr_cc) else np.nan

    breach_returns = frame.loc[violations == 1, "return_pct"]
    breach_es = frame.loc[violations == 1, "es_pct"]
    avg_realised_tail = float(breach_returns.mean()) if not breach_returns.empty else np.nan
    avg_forecast_es_on_breach = float(breach_es.mean()) if not breach_es.empty else np.nan
    fz = fz0_es_score(frame["return_pct"], frame["var_pct"], frame["es_pct"])

    return {
        "asset": asset,
        "model": model,
        "n_obs": int(len(frame)),
        "violations": int(violations.sum()),
        "expected_violations": float(len(frame) * ALPHA),
        "violation_rate_pct": float(100.0 * violations.mean()),
        "violation_rate_gap_pp": float(100.0 * (violations.mean() - ALPHA)),
        "avg_var_pct": float(frame["var_pct"].mean()),
        "avg_es_pct": float(frame["es_pct"].mean()),
        "std_var_forecast_pct": float(frame["var_pct"].std()),
        "std_es_forecast_pct": float(frame["es_pct"].std()),
        "avg_realised_return_on_violations_pct": avg_realised_tail,
        "avg_forecast_es_on_violations_pct": avg_forecast_es_on_breach,
        "kupiec_lr_uc": float(lr_uc),
        "kupiec_p_value": float(p_uc),
        "christoffersen_lr_ind": float(lr_ind),
        "christoffersen_p_value": float(p_ind),
        "conditional_coverage_lr": float(lr_cc),
        "conditional_coverage_p_value": float(p_cc),
        **fz,
        **transitions,
        "valid_transitions": pair_count,
        "omitted_gap_transitions": len(violations) - 1 - pair_count,
        "kupiec_result_5pct": _test_verdict(p_uc),
        "independence_result_5pct": _test_verdict(p_ind),
        "conditional_coverage_result_5pct": _test_verdict(p_cc),
    }


def evaluate_by_period(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Repete os backtests em regimes temporais predefinidos."""
    periods = {
        "pre_covid_2015_2019": ("2015-01-01", "2019-12-31"),
        "covid_2020_2021": ("2020-02-01", "2021-12-31"),
        "recent_2022_onward": ("2022-01-01", None),
    }
    rows: list[dict[str, Any]] = []
    data = forecasts.copy()
    data["date"] = pd.to_datetime(data["date"])
    for period_name, (start, end) in periods.items():
        mask = data["date"] >= pd.Timestamp(start)
        if end is not None:
            mask &= data["date"] <= pd.Timestamp(end)
        subset = data.loc[mask]
        for (asset, model), group in subset.groupby(["asset", "model"]):
            group = group.sort_values("date")
            idx = pd.DatetimeIndex(group["date"])
            r = pd.Series(group["return_pct"].to_numpy(dtype=float), index=idx)
            v = pd.Series(group["var_pct"].to_numpy(dtype=float), index=idx)
            e = pd.Series(group["es_pct"].to_numpy(dtype=float), index=idx)
            try:
                result = evaluate_forecasts(asset, model, r, ForecastSet(v, e), min_obs=MIN_PERIOD_OBS)
                result["period"] = period_name
                rows.append(result)
            except RuntimeError as exc:
                LOG.warning("Periodo ignorado (%s/%s/%s): %s", period_name, asset, model, exc)
    return pd.DataFrame(rows)


def _normalise_label(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _normalise_model(value: Any) -> str:
    key = _normalise_label(value)
    if "simulacaohistorica" in key:
        return "Simulacao historica"
    if "ewma" in key:
        return "EWMA normal"
    if "gjrgarch" in key:
        return "GJR-GARCH t"
    return str(value)


def compare_phase1_phase2(phase2_metrics: pd.DataFrame) -> pd.DataFrame:
    """Compara p-valores de Kupiec da Fase 1 e da Fase 2 quando o CSV existe."""
    phase1_runs = sorted((ROOT / "outputs" / "phase1" / "runs").glob("*/resultados_var.csv"))
    phase1_path = phase1_runs[-1] if phase1_runs else ROOT / "outputs" / "resultados_var.csv"
    if not phase1_path.exists():
        LOG.warning("CSV da Fase 1 nao encontrado em %s; comparacao sera ignorada.", phase1_path)
        return pd.DataFrame()
    try:
        old = pd.read_csv(phase1_path, encoding="utf-8-sig")
    except Exception as exc:
        LOG.warning("Nao foi possivel ler resultados da Fase 1: %s", exc)
        return pd.DataFrame()

    required = {"ativo", "modelo", "p_valor_kupiec"}
    if not required.issubset(old.columns):
        LOG.warning("CSV da Fase 1 nao tem as colunas esperadas: %s", sorted(required))
        return pd.DataFrame()

    old = old.copy()
    old["asset_key"] = old["ativo"].map(_normalise_label)
    old["model_key"] = old["modelo"].map(_normalise_model)
    old["phase1_kupiec_p_value"] = pd.to_numeric(old["p_valor_kupiec"], errors="coerce")
    old["n_obs_phase1"] = pd.to_numeric(old.get("n_obs"), errors="coerce")

    new = phase2_metrics[phase2_metrics["asset"] != "PORTFOLIO_50_50"].copy()
    if new.empty:
        return pd.DataFrame()
    new["asset_key"] = new["asset"].map(_normalise_label)
    new["model_key"] = new["model"].map(_normalise_model)
    new = new.rename(columns={"n_obs": "n_obs_phase2"})
    keep_new = [
        "asset", "model", "n_obs_phase2", "kupiec_p_value",
        "christoffersen_p_value", "conditional_coverage_p_value", "fz0_score_mean",
        "asset_key", "model_key",
    ]
    keep_old = ["asset_key", "model_key", "n_obs_phase1", "phase1_kupiec_p_value"]
    merged = new[keep_new].merge(old[keep_old], on=["asset_key", "model_key"], how="left")
    merged["kupiec_p_value_change"] = (
        merged["kupiec_p_value"] - merged["phase1_kupiec_p_value"]
    )
    return merged.drop(columns=["asset_key", "model_key"])


def build_portfolio_log_returns(
    price_series: dict[str, pd.Series], weights_dict: dict[str, float]
) -> pd.Series:
    """Cria retorno da carteira ponderando retornos simples, depois converte para log.

    Os pesos sao constantes por dia (rebalanceamento diario implicito).
    """
    if not weights_dict:
        raise ValueError("Informe ao menos um ativo na carteira.")
    total_weight = float(sum(weights_dict.values()))
    if not np.isclose(total_weight, 1.0, atol=1e-8):
        raise ValueError(f"Os pesos precisam somar 1.0; soma atual: {total_weight:.8f}")
    if any((not np.isfinite(w)) or w < 0 for w in weights_dict.values()):
        raise ValueError("Os pesos devem ser finitos e nao negativos nesta versao.")
    missing = [name for name in weights_dict if name not in price_series]
    if missing:
        raise KeyError(f"Precos ausentes para ativos da carteira: {missing}")

    prices = pd.concat(
        [price_series[name].rename(name) for name in weights_dict], axis=1, join="outer"
    )
    if len(prices) < 2:
        raise ValueError("Dados de preco insuficientes para calcular a carteira.")
    simple_returns = session_prices(prices).pct_change(fill_method=None).dropna()
    weights = pd.Series(weights_dict, dtype=float)
    portfolio_simple = simple_returns.mul(weights, axis=1).sum(axis=1)
    if (portfolio_simple <= -1.0).any():
        raise ValueError("Retorno simples da carteira menor ou igual a -100%; verifique os dados.")
    result = (100.0 * np.log1p(portfolio_simple)).replace([np.inf, -np.inf], np.nan).dropna()
    result.name = "PORTFOLIO_50_50"
    return result


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


def write_report(
    metrics: pd.DataFrame,
    diagnostics: pd.DataFrame,
    prices_info: dict[str, int],
    period_metrics: pd.DataFrame | None = None,
) -> None:
    report_path = OUTPUT_DIR / "phase2_report.md"
    lines = [
        "# RiskAgent B3 — Relatorio da Fase 2.1",
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
        "- `fz0_score_mean` e uma pontuacao conjunta VaR/ES: menor e melhor. Nao e p-valor nem teste de rejeicao.",
        "- As comparacoes por periodo usam janelas fixas; resultados dependem da amostra disponivel.",
        "",
        "## Correcao para multiplas comparacoes",
        "",
        "- Confirmatorio: nos resultados fora da amostra completos, cada familia agrega todos os ativos/modelos para um mesmo teste (Kupiec UC, Christoffersen IND ou cobertura condicional CC); p-valores originais sao mantidos e Holm controla o erro familiar.",
        "- Exploratorio: nos resultados por periodo, cada familia agrega periodos, ativos e modelos para um mesmo teste (UC, IND ou CC); Benjamini-Hochberg controla a taxa de falsas descobertas sob independencia ou dependencia positiva apropriada.",
        "- Sob dependencia arbitraria entre testes, o controle FDR do Benjamini-Hochberg nao e garantido.",
        "- Scores FZ0 nao sao p-valores e nao recebem ajuste.",
        "",
        "## Resultados por ativo/modelo",
        "",
    ]
    if metrics.empty:
        lines.append("Nenhuma combinacao teve amostra suficiente para avaliacao.")
    else:
        cols = [
            "asset", "model", "n_obs", "violations", "violation_rate_pct", "avg_var_pct", "avg_es_pct",
            "kupiec_p_value", "kupiec_p_value_holm", "christoffersen_p_value", "christoffersen_p_value_holm",
            "conditional_coverage_p_value", "conditional_coverage_p_value_holm",
        ]
        view = metrics[cols].copy()
        lines.append("```text")
        lines.append(view.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
        lines.append("```")
    if period_metrics is not None and not period_metrics.empty:
        period_cols = [
            "period", "asset", "model", "n_obs", "kupiec_p_value", "kupiec_p_value_bh",
            "christoffersen_p_value", "christoffersen_p_value_bh",
            "conditional_coverage_p_value", "conditional_coverage_p_value_bh",
        ]
        lines += ["", "## Resultados exploratorios por periodo (p-valores originais e BH)", "", "```text"]
        lines.append(period_metrics[period_cols].to_string(index=False, float_format=lambda value: f"{value:.4f}"))
        lines.append("```text")
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
        "- `phase2_metrics.csv`: metricas, backtests de VaR e score FZ0 de VaR/ES.",
        "- `phase2_es_scoring.csv`: resumo do score conjunto VaR/ES (FZ0; menor e melhor).",
        "- `phase2_period_metrics.csv`: backtests separados por periodo de mercado.",
        "- `phase2_phase1_comparison.csv`: comparacao com a Fase 1, quando o CSV antigo existe.",
        "- `phase2_forecasts.csv`: previsoes diarias de VaR e ES.",
        "- `phase2_garch_diagnostics.csv`: convergencia das estimacoes GJR-GARCH.",
        "- `manifest.json`: proveniencia, verificacoes basicas, hash do cache e versoes das bibliotecas.",
        "- `phase2_portfolio_weights.csv`: pesos usados na carteira demonstrativa.",
        "- `phase2_portfolio_var.png`, `phase2_portfolio_es.png` e `phase2_backtest_exceptions.png`: graficos.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    global OUTPUT_DIR
    parser = argparse.ArgumentParser(description="RiskAgent B3 - Fase 2.1")
    market_data.add_data_arguments(parser)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_started = pd.Timestamp.now(tz="UTC")
    run_stamp = run_started.strftime("run_%Y%m%dT%H%M%S_%fZ")
    OUTPUT_DIR = OUTPUT_ROOT / "runs" / run_stamp
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if arch_model is None:
        raise SystemExit("Dependencia ausente: arch. Execute: py -m pip install arch")
    inputs = {
        asset: _load_input(asset, ticker, strict_cache=args.strict_cache, offline=args.offline,
                           max_stale_sessions=args.max_stale_sessions, as_of=run_started, run_dir=OUTPUT_DIR)
        for asset, ticker in ASSETS.items()
    }
    price_series = {asset: data.prices for asset, data in inputs.items()}
    returns = {asset: data.returns for asset, data in inputs.items()}

    # Carteira 50/50: pesos aplicados a retornos simples, nao a log-retornos.
    portfolio_returns = build_portfolio_log_returns(price_series, PORTFOLIO_WEIGHTS)
    if len(portfolio_returns) < MIN_TOTAL_RETURNS:
        reason = f"Amostra comum insuficiente para a carteira: {len(portfolio_returns)} retornos."
        market_data.write_json(OUTPUT_DIR / "data_failure.json", {"status": "interrupted", "asset": portfolio_returns.name, "reason": reason})
        raise RuntimeError(reason)
    returns[portfolio_returns.name] = portfolio_returns

    write_data_manifest(
        OUTPUT_DIR / "manifest.json",
        run_id=OUTPUT_DIR.name,
        assets=ASSETS,
        prices=price_series,
        returns={asset: data.returns for asset, data in inputs.items()},
        input_records={asset: data.record for asset, data in inputs.items()},
        data_directory=DATA_DIR,
        sources=DATA_SOURCES,
        settings={
            "alpha": ALPHA,
            "window": WINDOW,
            "min_test_obs": MIN_TEST_OBS,
            "garch_refit_every": GARCH_REFIT_EVERY,
            "portfolio_weights": PORTFOLIO_WEIGHTS,
        },
    )

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
    write_extensions(OUTPUT_DIR, forecasts, returns, PORTFOLIO_WEIGHTS, ALPHA, adjust_pvalues)
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

    metrics = add_adjusted_pvalues(
        pd.DataFrame(metric_rows),
        ["kupiec_p_value", "christoffersen_p_value", "conditional_coverage_p_value"],
        "holm",
    )
    metrics.to_csv(OUTPUT_DIR / "phase2_metrics.csv", index=False, float_format="%.8f")
    es_cols = [c for c in ["asset", "model", "n_obs", "fz0_obs", "fz0_score_mean", "fz0_score_median", "avg_es_pct", "std_es_forecast_pct"] if c in metrics.columns]
    metrics[es_cols].to_csv(OUTPUT_DIR / "phase2_es_scoring.csv", index=False, float_format="%.8f")

    period_metrics = add_adjusted_pvalues(
        evaluate_by_period(forecasts),
        ["kupiec_p_value", "christoffersen_p_value", "conditional_coverage_p_value"],
        "bh",
    )
    period_metrics.to_csv(OUTPUT_DIR / "phase2_period_metrics.csv", index=False, float_format="%.8f")

    phase_comparison = compare_phase1_phase2(metrics)
    if not phase_comparison.empty:
        phase_comparison.to_csv(OUTPUT_DIR / "phase2_phase1_comparison.csv", index=False, float_format="%.8f")

    diagnostics_frame = pd.DataFrame(all_diagnostics)
    diagnostics_frame.to_csv(OUTPUT_DIR / "phase2_garch_diagnostics.csv", index=False)

    portfolio_table = forecasts[forecasts["asset"] == "PORTFOLIO_50_50"].copy()
    plot_portfolio(portfolio_table)
    write_report(
        metrics,
        diagnostics_frame,
        {name: len(values) for name, values in price_series.items()},
        period_metrics,
    )


    print("\nFASE 2 CONCLUIDA")
    print(f"Resultados salvos em: {OUTPUT_DIR}")
    print("Arquivos principais:")
    for filename in [
        "phase2_metrics.csv",
        "phase2_es_scoring.csv",
        "phase2_period_metrics.csv",
        "phase2_phase1_comparison.csv (se houver resultados da Fase 1)",
        "phase2_forecasts.csv",
        "phase2_garch_diagnostics.csv",
        "phase2_portfolio_weights.csv",
        "phase2_report.md",
        "phase2_portfolio_var.png",
        "phase2_portfolio_es.png",
        "phase2_backtest_exceptions.png",
        "manifest.json",
    ]:
        print(f" - {filename}")
    if not metrics.empty:
        display_cols = ["asset", "model", "n_obs", "violations", "violation_rate_pct", "kupiec_p_value", "christoffersen_p_value", "conditional_coverage_p_value"]
        print("\nResumo dos backtests:")
        print(metrics[display_cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    if not period_metrics.empty:
        cols = ["period", "asset", "model", "n_obs", "kupiec_p_value", "christoffersen_p_value", "conditional_coverage_p_value", "fz0_score_mean"]
        print("\nResumo por periodo (FZ0 menor e melhor; nao e p-valor):")
        print(period_metrics[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    successful = int((diagnostics_frame["status"] == "ok").sum()) if not diagnostics_frame.empty else 0
    total = len(diagnostics_frame)
    print(f"\nEstimativas GJR-GARCH convergentes: {successful}/{total}")


if __name__ == "__main__":
    main()
