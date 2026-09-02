"""Small set of causal (no-lookahead) indicator functions shared by the
spec evaluator (`app/backtesting/spec_evaluator.py`) and mirrored as
generated text in `app/codegen/python_gen.py`'s standalone output. Every
function here only ever looks at the current bar and earlier."""

from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(
        axis=1
    )
    return tr.rolling(length).mean()


def session_vwap(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, session_date
) -> pd.Series:
    typical = (high + low + close) / 3.0
    pv = typical * volume
    grouped_pv = pv.groupby(session_date).cumsum()
    grouped_vol = volume.groupby(session_date).cumsum()
    return grouped_pv / grouped_vol.replace(0, pd.NA)
