"""
var_baseline.py — Fase 1 do RiskAgent B3

Compara três modelos de VaR 99% (Simulação Histórica, EWMA e GJR-GARCH com
t-Student) em PETR4, VALE3 e Ibovespa, com backtest fora da amostra e teste
de Kupiec.

Uso:   python src/var_baseline.py
Saída: outputs/phase1/runs/<id>/ com métricas, diagnósticos, manifest e gráficos.
"""
from pathlib import Path
import argparse
import json
import logging
import sys
import warnings

import matplotlib

matplotlib.use("Agg")  # salva o PNG sem abrir janela
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model
from scipy import stats
from scipy.special import xlogy

if __package__:
    from . import market_data
    from .b3_sessions import daily_log_returns
    from .data_manifest import write_data_manifest
else:
    import market_data
    from b3_sessions import daily_log_returns
    from data_manifest import write_data_manifest

# ── Configuração ─────────────────────────────────────────────────────────────
ATIVOS = {"PETR4": "PETR4.SA", "VALE3": "VALE3.SA", "IBOV": "^BVSP"}
INICIO = "2010-01-01"
ALPHA = 0.01           # VaR 99% → olhamos o 1% pior dos retornos
JANELA = 1000          # ≈ 4 anos de pregões usados para estimar cada modelo
REESTIMAR_A_CADA = 20  # reajusta o GARCH a cada ~1 mês (mais rápido)
LAMBDA = 0.94          # decaimento do EWMA (padrão RiskMetrics)
MIN_TEST_OBS = 250
MIN_RETURNS = JANELA + MIN_TEST_OBS
CACHE_OVERLAP_DAYS = 5
PLOT_DE, PLOT_ATE = "2019-10-01", "2020-12-31"  # zoom na crise da covid

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data" / "raw"
SAIDA_RAIZ = RAIZ / "outputs"
SAIDA = SAIDA_RAIZ
DATA_SOURCES: dict[str, str] = {}


# ── Dados ────────────────────────────────────────────────────────────────────
def _normalizar_precos(series: pd.Series, nome: str) -> pd.Series:
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    return market_data.clean_prices(series, nome, today)[0]


def _calcular_retornos(preco: pd.Series, nome: str) -> pd.Series:
    return daily_log_returns(preco).rename(nome)


def validar_amostra(retornos: pd.Series, nome: str = "ativo") -> None:
    if len(retornos) < MIN_RETURNS:
        raise RuntimeError(
            f"Amostra insuficiente para {nome}: {len(retornos)} retornos validos; "
            f"minimo exigido: {MIN_RETURNS} (janela {JANELA} + teste {MIN_TEST_OBS})."
        )


def _baixar_yahoo(ticker: str, start: str = INICIO) -> pd.Series:
    """Preço de fechamento ajustado; tenta yf.download e, se falhar, Ticker.history."""
    try:
        frame = yf.download(ticker, start=start, auto_adjust=True, progress=False, timeout=15)
        if not frame.empty and "Close" not in frame:
            return frame
        px = frame["Close"]
        if isinstance(px, pd.DataFrame):  # versões novas do yfinance
            px = px.iloc[:, 0]
        if px.dropna().size > 0:
            return px
    except Exception as erro:
        print(f"  yf.download falhou ({erro}); tentando outro método...")
    frame = yf.Ticker(ticker).history(start=start, auto_adjust=True, timeout=15)
    return frame["Close"] if "Close" in frame else frame


def _load_input(nome: str, ticker: str, tentativas: int = 4, strict_cache: bool = False, **options):
    result = market_data.ingest(
        nome, cache_path=DADOS / f"{nome}.csv", start=INICIO,
        minimum=MIN_RETURNS, overlap_days=CACHE_OVERLAP_DAYS,
        symbol=ticker, fetch=lambda start: _baixar_yahoo(ticker, start=start),
        attempts=tentativas, strict=strict_cache, **options,
    )
    DATA_SOURCES[nome] = result.record["source_mode"]
    return result


def baixar_retornos(nome: str, ticker: str, tentativas: int = 4, strict_cache: bool = False, **options) -> pd.Series:
    """Atualiza o cache e devolve retornos entre dois pregões consecutivos."""
    return _load_input(nome, ticker, tentativas, strict_cache, **options).returns


# ── Modelos: cada um prevê o VaR do dia t usando apenas dados até t-1 ────────
def var_historico(r: pd.Series) -> pd.Series:
    """Simulação histórica: quantil empírico dos últimos JANELA retornos."""
    return r.rolling(JANELA).quantile(ALPHA).shift(1)


def var_ewma(r: pd.Series) -> pd.Series:
    """EWMA (RiskMetrics): volatilidade exponencial × quantil da normal."""
    sigma = np.sqrt(r.pow(2).ewm(alpha=1 - LAMBDA, adjust=False).mean().shift(1))
    return stats.norm.ppf(ALPHA) * sigma


def var_gjr_garch_t(r: pd.Series, ativo: str = "asset") -> tuple[pd.Series, list[dict]]:
    """GJR-GARCH(1,1)-t com previsoes por bloco e registro de convergencia."""
    out = pd.Series(np.nan, index=r.index)
    diagnostics: list[dict] = []
    spec = dict(mean="Zero", vol="GARCH", p=1, o=1, q=1, dist="t")
    for start in range(JANELA, len(r), REESTIMAR_A_CADA):
        stop = min(start + REESTIMAR_A_CADA, len(r))
        fit_sample = r.iloc[start - JANELA:start]
        row = {
            "asset": ativo,
            "fit_start": str(fit_sample.index[0].date()),
            "fit_end": str(fit_sample.index[-1].date()),
            "forecast_start": str(r.index[start].date()),
            "forecast_end": str(r.index[stop - 1].date()),
            "optimization_method": "SLSQP (arch default)",
            "iterations": np.nan,
            "log_likelihood": np.nan,
            "convergence_flag": np.nan,
            "nu": np.nan,
            "parameters_json": "",
            "status": "failed",
            "message": "",
        }
        caught = []
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                ajuste = arch_model(fit_sample, **spec).fit(disp="off", show_warning=False)
            flag = getattr(ajuste, "convergence_flag", None)
            if flag is None:
                raise RuntimeError("Resultado do ajuste sem indicador de convergencia.")
            row["convergence_flag"] = int(flag)
            optimization_result = getattr(ajuste, "optimization_result", None)
            row["iterations"] = getattr(optimization_result, "nit", np.nan)
            row["log_likelihood"] = float(ajuste.loglikelihood)
            if row["convergence_flag"] != 0:
                raise RuntimeError(f"Otimizador nao convergiu (flag={row['convergence_flag']}).")

            nu = float(ajuste.params["nu"])
            row["nu"] = nu
            if not np.isfinite(nu) or nu <= 2.0:
                raise ValueError(f"Graus de liberdade invalidos para t-Student: {nu}")
            row["parameters_json"] = json.dumps(
                {key: float(value) for key, value in ajuste.params.items()}, sort_keys=True
            )
            bloco = r.iloc[start - JANELA:stop]
            sigma = arch_model(bloco, **spec).fix(ajuste.params).conditional_volatility.iloc[JANELA:].to_numpy(dtype=float)
            if len(sigma) != stop - start or not np.isfinite(sigma).all() or (sigma <= 0).any():
                raise RuntimeError("Volatilidade condicional invalida no bloco GJR-GARCH.")
            z = stats.t.ppf(ALPHA, nu) * np.sqrt((nu - 2.0) / nu)
            out.iloc[start:stop] = z * sigma
            row["status"] = "ok"
            row["message"] = " | ".join(str(warning.message) for warning in caught[-2:])
        except Exception as erro:
            out.iloc[start:stop] = np.nan
            row["message"] = str(erro)[:500]
            logging.warning("GJR-GARCH falhou em %s, bloco %s: %s", ativo, row["fit_end"], erro)
        diagnostics.append(row)
    return out, diagnostics


# ── Backtest ─────────────────────────────────────────────────────────────────
def kupiec(violacoes: pd.Series) -> tuple[float, float]:
    """Teste de Kupiec. H0: a taxa de violações é igual a ALPHA."""
    n, x = len(violacoes), int(violacoes.sum())
    if n == 0:
        return float("nan"), float("nan")
    if not 0.0 < ALPHA < 1.0:
        raise ValueError("ALPHA deve estar estritamente entre 0 e 1.")
    p_obs = x / n
    ll_null = xlogy(x, ALPHA) + xlogy(n - x, 1.0 - ALPHA)
    ll_alt = xlogy(x, p_obs) + xlogy(n - x, 1.0 - p_obs)
    lr = max(0.0, float(2.0 * (ll_alt - ll_null)))
    return lr, float(stats.chi2.sf(lr, df=1))


def avaliar(ativo: str, r: pd.Series, vars_: dict) -> list[dict]:
    linhas = []
    for modelo, v in vars_.items():
        base = pd.concat([r, v], axis=1, keys=["ret", "var"]).dropna()
        if base.empty:
            linhas.append({
                "ativo": ativo,
                "modelo": modelo,
                "n_obs": 0,
                "violações": 0,
                "esperadas": 0.0,
                "taxa_%": float("nan"),
                "var_médio_%": float("nan"),
                "p_valor_kupiec": float("nan"),
                "veredito": "indisponível",
            })
            continue
        viol = base["ret"] < base["var"]  # perda maior que o VaR previsto
        _, p = kupiec(viol)
        linhas.append({
            "ativo": ativo,
            "modelo": modelo,
            "n_obs": len(base),
            "violações": int(viol.sum()),
            "esperadas": round(len(base) * ALPHA, 1),
            "taxa_%": round(100 * viol.mean(), 2),
            "var_médio_%": round(base["var"].mean(), 2),
            "p_valor_kupiec": round(p, 3),
            "veredito": "não rejeitado" if p >= 0.05 else "rejeitado",
        })
    return linhas


def grafico(ativo: str, r: pd.Series, vars_: dict) -> None:
    """Zoom na crise de 2020: onde cada modelo errou?"""
    zoom = slice(PLOT_DE, PLOT_ATE)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(r.loc[zoom], color="lightgray", lw=0.8, label="retorno diário (%)")
    for modelo, v in vars_.items():
        (linha,) = ax.plot(v.loc[zoom], lw=1.4, label=f"VaR 99% — {modelo}")
        ret, var = r.loc[zoom], v.loc[zoom]
        violacoes = ret[ret < var]
        ax.scatter(violacoes.index, violacoes, marker="x", s=40,
                   color=linha.get_color(), zorder=3)
    ax.set_title(f"{ativo} — VaR 99% (× = violação)")
    ax.set_ylabel("%")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.savefig(SAIDA / f"var_2020_{ativo}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    global SAIDA
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="RiskAgent B3 - Fase 1")
    market_data.add_data_arguments(parser)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_started = pd.Timestamp.now(tz="UTC")
    run_stamp = run_started.strftime("run_%Y%m%dT%H%M%S_%fZ")
    SAIDA = SAIDA_RAIZ / "phase1" / "runs" / run_stamp
    SAIDA.mkdir(parents=True, exist_ok=True)
    linhas = []
    inputs = {
        asset: _load_input(asset, ticker, strict_cache=args.strict_cache, offline=args.offline,
                           max_stale_sessions=args.max_stale_sessions, as_of=run_started, run_dir=SAIDA)
        for asset, ticker in ATIVOS.items()
    }
    write_data_manifest(
        SAIDA / "manifest.json",
        run_id=SAIDA.name,
        assets=ATIVOS,
        prices={asset: data.prices for asset, data in inputs.items()},
        returns={asset: data.returns for asset, data in inputs.items()},
        input_records={asset: data.record for asset, data in inputs.items()},
        data_directory=DADOS,
        sources=DATA_SOURCES,
        settings={
            "alpha": ALPHA,
            "window": JANELA,
            "min_test_obs": MIN_TEST_OBS,
            "garch_refit_every": REESTIMAR_A_CADA,
            "ewma_lambda": LAMBDA,
        },
    )

    all_garch_diagnostics: list[dict] = []
    for ativo, data in inputs.items():
        r = data.returns
        print(f"▶ {ativo}: ajustando modelos com {len(r)} retornos diários...")
        gjr_var, garch_diagnostics = var_gjr_garch_t(r, ativo)
        all_garch_diagnostics.extend(garch_diagnostics)
        vars_ = {
            "Simulação histórica": var_historico(r),
            "EWMA (normal)": var_ewma(r),
            "GJR-GARCH-t": gjr_var,
        }
        # amostra comum a todos os modelos: só depois da primeira janela
        vars_ = {m: v.iloc[JANELA:] for m, v in vars_.items()}
        linhas += avaliar(ativo, r, vars_)
        grafico(ativo, r, vars_)

    tabela = pd.DataFrame(linhas)
    tabela.to_csv(SAIDA / "resultados_var.csv", index=False)
    pd.DataFrame(all_garch_diagnostics).to_csv(SAIDA / "garch_diagnostics.csv", index=False)
    print("\n" + tabela.to_string(index=False))
    print(f"\nArquivos salvos em: {SAIDA}")


if __name__ == "__main__":
    main()
