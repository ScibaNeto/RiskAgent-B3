"""Calendário de pregões e retornos diários usados pelas duas fases."""
from functools import lru_cache

import exchange_calendars as xcals
import numpy as np
import pandas as pd


@lru_cache(maxsize=8)
def _schedule(first_year: int, last_year: int) -> pd.DataFrame:
    return xcals.get_calendar(
        "BVMF", start=f"{first_year}-01-01", end=f"{last_year}-12-31"
    ).schedule


def completed_sessions(start: str, as_of: pd.Timestamp) -> pd.DatetimeIndex:
    """Só inclui sessões cujo fechamento programado já ocorreu no instante de corte."""
    beginning = pd.Timestamp(start)
    cutoff = as_of.tz_convert("UTC")
    local_day = cutoff.tz_convert("America/Sao_Paulo").tz_localize(None).normalize()
    if beginning > local_day:
        raise ValueError("Data inicial posterior ao corte da execução.")
    schedule = _schedule(beginning.year, local_day.year).loc[beginning:local_day]
    return schedule.index[schedule["close"] <= cutoff]


def session_prices(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """Expõe lacunas como NaN e exclui observações fora do calendário de negociação."""
    if prices.empty:
        return prices
    start, end = prices.index.min(), prices.index.max()
    sessions = _schedule(start.year, end.year).loc[start:end].index
    return prices.reindex(sessions)


def daily_log_returns(prices: pd.Series) -> pd.Series:
    closes = session_prices(prices)
    return (100 * np.log(closes / closes.shift(1))).replace([np.inf, -np.inf], np.nan).dropna()
