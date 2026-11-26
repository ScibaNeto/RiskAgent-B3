"""Sensibilidade local do VaR no primeiro retorno observado após uma lacuna."""
import json

import numpy as np
import pandas as pd
from scipy.stats import t

if __package__:
    from .b3_sessions import session_prices
else:
    from b3_sessions import session_prices


def expected_gap_var(var, params, alpha, missing):
    """Propaga a variância esperada de um GJR-t simétrico por sessões sem retorno."""
    nu = params["nu"]
    quantile = t.ppf(alpha, nu) * np.sqrt((nu - 2) / nu)
    variance = (var / quantile) ** 2
    persistence = params["alpha[1]"] + params["gamma[1]"] / 2 + params["beta[1]"]
    for _ in range(missing):
        variance = params["omega"] + persistence * variance
    return quantile * np.sqrt(variance)


def gap_sensitivity(forecasts, diagnostics, alpha):
    columns = ["asset", "model", "date", "missing_sessions", "status", "return_pct",
               "baseline_var_pct", "expected_variance_var_pct"]
    rows = []
    for (asset, model), frame in forecasts.groupby(["asset", "model"]):
        if model not in ("EWMA normal", "GJR-GARCH t"):
            continue
        data = frame.set_index(pd.to_datetime(frame.date)).sort_index()
        observed = data.loc[data.return_pct.notna()]
        sessions = session_prices(observed.return_pct).index
        positions = pd.Series(sessions.get_indexer(observed.index), index=observed.index)
        if (positions < 0).any() or observed.index.has_duplicates:
            raise ValueError("Retornos fora do calendário ou datas duplicadas.")
        skips = positions.diff() - 1
        for date, gap in skips[skips > 0].items():
            date_text = date.date().isoformat()
            baseline = observed.at[date, "var_pct"]
            candidate = baseline
            status = "ok" if np.isfinite(baseline) else "previsao_indisponivel"
            if model == "GJR-GARCH t" and status == "ok":
                block = diagnostics.loc[(diagnostics.asset == asset) & (diagnostics.status == "ok")
                                        & (diagnostics.fit_end < date_text)
                                        & (diagnostics.forecast_start <= date_text)
                                        & (diagnostics.forecast_end >= date_text)]
                if len(block) != 1:
                    status, candidate = "ajuste_indisponivel", np.nan
                else:
                    params = json.loads(block.iloc[0].parameters_json)
                    candidate = expected_gap_var(baseline, params, alpha, int(gap))
            rows.append((asset, model, date_text, int(gap), status, observed.at[date, "return_pct"],
                         baseline, candidate))
    return pd.DataFrame(rows, columns=columns)
