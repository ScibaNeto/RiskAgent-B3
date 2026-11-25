"""Diagnósticos adicionais de cauda e cenários de um pregão da carteira."""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

if __package__:
    from .b3_sessions import session_prices
else:
    from b3_sessions import session_prices


def hac_standard_error(moment: pd.Series, lags: int) -> float:
    """Erro padrão da média com pesos Bartlett e blocos de pregões consecutivos."""
    observed = moment.dropna()
    if len(observed) < 2 or lags < 0:
        return np.nan
    centered = (moment - observed.mean()).to_numpy(dtype=float)
    # Um identificador novo para cada quebra evita até pares que saltam a lacuna.
    blocks = np.cumsum(~np.isfinite(centered))
    variance = np.nansum(centered**2)
    for lag in range(1, min(lags + 1, len(centered))):
        pairs = blocks[lag:] == blocks[:-lag]
        products = centered[lag:] * centered[:-lag]
        variance += 2 * (1 - lag / (lags + 1)) * np.nansum(products[pairs])
    return np.sqrt(max(0.0, variance)) / len(observed)


def es_inference(group: pd.DataFrame, alpha: float) -> dict:
    """Teste unilateral assintótico do momento incondicional de cauda."""
    frame = group.set_index(pd.to_datetime(group["date"])).sort_index()
    if frame.index.has_duplicates:
        raise ValueError("Datas duplicadas na inferência de ES.")
    data = frame[["return_pct", "var_pct", "es_pct"]].replace([np.inf, -np.inf], np.nan).dropna()
    valid = data.loc[(data.es_pct < 0) & (data.es_pct <= data.var_pct)]
    hits = valid.return_pct < valid.var_pct
    moments = 1 - (valid.return_pct / valid.es_pct) * hits / alpha
    calendar = session_prices(moments)
    if not moments.index.isin(calendar.index).all():
        raise ValueError("Observação fora do calendário BVMF.")
    n = len(moments)
    lags = int(np.floor(4 * (n / 100) ** (2 / 9)))
    result = {"es_valid_breaches": int(hits.sum()), "hac_lags": lags,
              "hac_se": np.nan, "es_p_lower": np.nan, "es_test_status": "amostra_insuficiente"}
    if n * alpha < 20 or hits.sum() < 10:
        return result
    se = hac_standard_error(calendar, lags)
    if not np.isfinite(se) or se <= 0:
        result["es_test_status"] = "variancia_indisponivel"
        return result
    return dict(result, hac_se=se, es_p_lower=float(norm.cdf(moments.mean() / se)), es_test_status="calculado")



def tail_summary(group: pd.DataFrame, alpha: float) -> dict:
    data = group[["return_pct", "var_pct", "es_pct"]].replace([np.inf, -np.inf], np.nan).dropna()
    if data.empty:
        return {"n": 0, "breaches": 0}
    hits = data.return_pct < data.var_pct
    count = int(hits.sum())
    interval = binomtest(count, len(data)).proportion_ci(confidence_level=0.95, method="exact")
    # Unconditional normalized ES moment (negative if losses exceed the model on average).
    valid = (data.es_pct < 0) & (data.es_pct <= data.var_pct)
    normalized = ((data.return_pct[valid] / data.es_pct[valid]) * hits[valid]).mean()
    return {"n": len(data), "breaches": count, "hit_rate_ci_low": interval.low,
            "hit_rate_ci_high": interval.high, "es_valid_days": int(valid.sum()),
            "es_unconditional_z2": 1 - normalized / alpha if valid.any() else np.nan}


def portfolio_scenarios(returns: dict, weights: dict, joint_shocks: dict | None = None) -> pd.DataFrame:
    aligned = pd.concat({a: returns[a] for a in weights}, axis=1, join="inner").dropna()
    if aligned.empty:
        raise ValueError("Sem retornos comuns para o estresse.")
    simple = np.expm1(aligned / 100) * 100
    portfolio = simple.mul(pd.Series(weights)).sum(axis=1)
    worst = portfolio.idxmin()
    rows = [{"scenario": "pior pregão comum observado", "kind": "historico", "date": str(worst.date()),
             **simple.loc[worst].to_dict(), "portfolio_simple_pct": portfolio.loc[worst]}]
    # Choques ilustrativos de retorno simples, sem probabilidade atribuída.
    for asset in weights:
        shocks = {a: -10.0 if a == asset else 0.0 for a in weights}
        rows.append({"scenario": f"queda isolada de 10% em {asset}", "kind": "hipotetico", "date": None,
                     **shocks, "portfolio_simple_pct": sum(weights[a] * shocks[a] for a in weights)})
    for name, shocks in (joint_shocks or {}).items():
        if set(shocks) != set(weights) or any(not np.isfinite(s) or s < -100 for s in shocks.values()):
            raise ValueError("Choques devem cobrir cada posição com retorno simples válido.")
        rows.append({"scenario": name, "kind": "hipotetico", "date": None, **shocks,
                     "portfolio_simple_pct": sum(weights[a] * shocks[a] for a in weights)})
    return pd.DataFrame(rows)


def write_extensions(directory: Path, forecasts, returns, weights, alpha, adjust_pvalues):
    rows = [dict(asset=a, model=m, alpha=alpha, **tail_summary(g, alpha), **es_inference(g, alpha))
            for (a, m), g in forecasts.groupby(["asset", "model"])]
    tail = pd.DataFrame(rows)
    tail["es_p_lower_holm"] = adjust_pvalues(tail.es_p_lower, "holm")
    tail.to_csv(directory / "phase2_2_tail.csv", index=False)
    shocks = {"queda conjunta de 10%": dict.fromkeys(weights, -10.0)}
    if set(weights) == {"PETR4", "VALE3"}:
        shocks["quedas de 20% em PETR4 e 10% em VALE3"] = {"PETR4": -20.0, "VALE3": -10.0}
        shocks["PETR4 cai 15% e VALE3 sobe 5%"] = {"PETR4": -15.0, "VALE3": 5.0}
    portfolio_scenarios(returns, weights, shocks).to_csv(directory / "phase2_3_stress.csv", index=False)
