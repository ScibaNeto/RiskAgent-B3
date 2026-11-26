"""Estresse histórico de fatores com calibração fixa e insumos versionados."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .b3_sessions import daily_log_returns
else:
    from b3_sessions import daily_log_returns

REFERENCE = Path(__file__).resolve().parents[1] / "data/reference/bcb_sgs_1_2023_2024.json"
DIGEST = "cab43a26aed233c286e247a983e1538550f320fe8b34c41791b49808290483fa"


def exchange_returns():
    raw = REFERENCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise ValueError("A referência cambial diverge da versão registrada.")
    data = pd.DataFrame(json.loads(raw))
    series = pd.Series(data.valor.astype(float).to_numpy(), index=pd.to_datetime(data.data, format="%d/%m/%Y"))
    return daily_log_returns(series)


def factor_stress(returns, weights, fx):
    # Retornos simples em pontos percentuais. Choques deslocam fatores com resíduo zero.
    frame = pd.concat({**{k: returns[k] for k in weights}, "market": returns["IBOV"], "fx": fx}, axis=1)
    frame = 100 * np.expm1(frame.dropna() / 100)
    x = np.column_stack([np.ones(len(frame)), frame[["market", "fx"]]])
    if len(frame) < 60 or np.linalg.matrix_rank(x) < 3:
        raise ValueError("Histórico comum insuficiente ou fatores colineares.")
    rows = []
    for asset, weight in weights.items():
        _, market_beta, fx_beta = np.linalg.lstsq(x, frame[asset], rcond=None)[0]
        for market, dollar in [(0, 5), (-5, 0), (-5, 5)]:
            impact = market * market_beta + dollar * fx_beta
            rows.append(dict(asset=asset, weight=weight, market_shock_pct=market, fx_shock_pct=dollar,
                             market_beta=market_beta, fx_beta=fx_beta, impact_pct=impact,
                             contribution_pct=weight * impact, n=len(frame), start=frame.index.min().date(),
                             end=frame.index.max().date(), fx_sha256=DIGEST))
    result = pd.DataFrame(rows)
    result["portfolio_impact_pct"] = result.groupby(["market_shock_pct","fx_shock_pct"]).contribution_pct.transform("sum")
    return result
