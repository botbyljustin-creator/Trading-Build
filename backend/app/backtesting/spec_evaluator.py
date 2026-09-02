"""Evaluates a `StrategySpecification` directly against OHLCV data to
produce the `generate_signals`-shaped DataFrame the backtest engine
consumes — without generating, writing, or `exec`-ing any code.

This is the runtime counterpart to `app/codegen/python_gen.py`: that module
renders human-readable Python *text* for the user to download and run
elsewhere; this module performs the equivalent computation in-process so a
backtest can be run immediately after compiling a strategy version, using
the exact same condition semantics (`app/codegen/conditions.py`'s
`RECOGNIZED_CONDITION_TYPES` — kept in lockstep by
`tests/test_codegen_equivalence.py`). Exactly like the generators, any rule
without a recognized `machine_readable_rule.type` evaluates to an
always-False condition — a backtest never silently trades on a fabricated
interpretation of free-text source material.
"""

from __future__ import annotations

import pandas as pd

from app.backtesting.indicators import ema, session_vwap, sma
from app.schemas.strategy_spec import StrategySpecification

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def evaluate_condition(df: pd.DataFrame, machine_readable_rule: dict | None) -> pd.Series:
    mrr = machine_readable_rule or {}
    condition_type = mrr.get("type")
    close = df["close"]

    if condition_type == "price_above_ma":
        length = int(mrr.get("length", 200))
        ma_fn = ema if str(mrr.get("ma_type", "EMA")).upper() == "EMA" else sma
        return close > ma_fn(close, length)

    if condition_type == "price_below_ma":
        length = int(mrr.get("length", 200))
        ma_fn = ema if str(mrr.get("ma_type", "EMA")).upper() == "EMA" else sma
        return close < ma_fn(close, length)

    if condition_type in ("vwap_reclaim", "vwap_rejection"):
        vwap = session_vwap(df["high"], df["low"], close, df["volume"], df.index.date)
        if condition_type == "vwap_reclaim":
            return (close > vwap) & (close.shift(1) <= vwap.shift(1))
        return (close < vwap) & (close.shift(1) >= vwap.shift(1))

    if condition_type == "always_true":
        return pd.Series(True, index=df.index)

    # Unrecognized / free-text rule — never fabricate a condition.
    return pd.Series(False, index=df.index)


def _session_filter(df: pd.DataFrame, spec: StrategySpecification) -> pd.Series:
    if spec.session is None:
        return pd.Series(True, index=df.index)
    s = spec.session
    local_time = df.index.tz_convert(s.timezone)
    minutes = local_time.hour * 60 + local_time.minute
    start_h, start_m = (int(x) for x in s.start_time.split(":"))
    end_h, end_m = (int(x) for x in s.end_time.split(":"))
    start_minutes, end_minutes = start_h * 60 + start_m, end_h * 60 + end_m
    weekday_ok = local_time.weekday.isin(s.days_of_week)
    return pd.Series(
        (minutes >= start_minutes) & (minutes < end_minutes) & weekday_ok, index=df.index
    )


def _distance_series(df: pd.DataFrame, method: str | None, value: float | None) -> pd.Series:
    if method == "FIXED_POINTS" and value is not None:
        return pd.Series(value, index=df.index)
    if method == "FIXED_PERCENT" and value is not None:
        return df["close"] * (value / 100.0)
    if method == "ATR_MULTIPLE" and value is not None:
        from app.backtesting.indicators import atr

        return atr(df["high"], df["low"], df["close"], 14) * value
    return pd.Series(float("nan"), index=df.index)


def evaluate_spec_signals(spec: StrategySpecification, df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            raise ValueError(f"df is missing required column '{col}'")

    in_session = _session_filter(df, spec)
    bias = evaluate_condition(df, spec.bias_condition)
    setup = evaluate_condition(df, spec.setup_condition)
    confirmation = evaluate_condition(df, spec.confirmation_condition)
    entry = evaluate_condition(df, spec.entry_condition)

    base_signal = in_session & bias & setup & confirmation & entry

    long_entry = base_signal if spec.allow_long else pd.Series(False, index=df.index)
    short_entry = base_signal if spec.allow_short else pd.Series(False, index=df.index)

    stop_method = spec.stop_loss.method if spec.stop_loss else None
    stop_value = spec.stop_loss.value if spec.stop_loss else None
    stop_distance = _distance_series(df, stop_method, stop_value)

    if (
        spec.take_profit
        and spec.take_profit.method == "R_MULTIPLE"
        and spec.take_profit.value is not None
    ):
        target_distance = stop_distance * spec.take_profit.value
    else:
        target_method = spec.take_profit.method if spec.take_profit else None
        target_value = spec.take_profit.value if spec.take_profit else None
        target_distance = _distance_series(df, target_method, target_value)

    return pd.DataFrame(
        {
            "long_entry": long_entry,
            "short_entry": short_entry,
            "stop_distance": stop_distance,
            "target_distance": target_distance,
        },
        index=df.index,
    )
