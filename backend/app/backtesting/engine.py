"""Event-driven backtest engine (Modules 11-12).

Core invariant, enforced structurally rather than just by convention: a
decision made while processing bar `i` can only ever be filled using bar
`i + 1`'s open or later — never bar `i`'s own close or anything before it
existed. This is why entries are staged as a `_PendingEntry` at the end of
processing bar `i` and only filled at the very start of processing bar
`i + 1`, using that bar's `open`. `tests/test_backtest_no_lookahead.py`
verifies this with a truncation-invariance test: results up to time T must
be identical whether or not bars after T exist in the input at all.

The engine consumes exactly the shape `app/codegen/python_gen.py` emits
from `generate_signals(df)` — `long_entry`, `short_entry`, `stop_distance`,
`target_distance` — so a generated strategy can be run here without any
adaptation layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

import pandas as pd

REQUIRED_BAR_COLUMNS = ["open", "high", "low", "close", "volume"]
REQUIRED_SIGNAL_COLUMNS = ["long_entry", "short_entry", "stop_distance", "target_distance"]


@dataclass
class BacktestConfig:
    starting_balance: float
    commission_per_trade: float = 0.0
    commission_pct: float = 0.0
    slippage_pct: float = 0.0
    risk_pct_per_trade: float = 1.0
    allow_long: bool = True
    allow_short: bool = True
    max_trades_per_day: int | None = None
    allow_overnight: bool = True
    # If set (and allow_overnight is False), any open position is force-closed
    # at or after this local time, in `session_timezone`.
    session_end_time: time | None = None
    session_timezone: str = "UTC"


@dataclass
class Trade:
    direction: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float | None
    quantity: float
    pnl: float
    pnl_pct: float
    r_multiple: float
    exit_reason: str


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[pd.Timestamp, float]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _PendingEntry:
    direction: str
    stop_distance: float
    target_distance: float | None


def _validate_inputs(bars: pd.DataFrame, signals: pd.DataFrame) -> None:
    for col in REQUIRED_BAR_COLUMNS:
        if col not in bars.columns:
            raise ValueError(f"bars is missing required column '{col}'")
    for col in REQUIRED_SIGNAL_COLUMNS:
        if col not in signals.columns:
            raise ValueError(f"signals is missing required column '{col}'")
    if not bars.index.equals(signals.index):
        raise ValueError(
            "bars and signals must share the exact same index (same bars, same order)."
        )
    if not bars.index.is_monotonic_increasing:
        raise ValueError(
            "bars index must be sorted ascending — a backtest cannot run on shuffled time."
        )


def _forced_close_due(ts: pd.Timestamp, config: BacktestConfig) -> bool:
    if config.allow_overnight or config.session_end_time is None:
        return False
    local_ts = ts.tz_convert(config.session_timezone)
    return local_ts.time() >= config.session_end_time


def run_backtest(
    bars: pd.DataFrame, signals: pd.DataFrame, config: BacktestConfig
) -> BacktestResult:
    _validate_inputs(bars, signals)

    result = BacktestResult()
    equity = config.starting_balance
    position: dict | None = None
    pending: _PendingEntry | None = None
    trades_today: dict[date, int] = {}

    n = len(bars)
    opens, highs, lows, closes = (bars[c] for c in ["open", "high", "low", "close"])

    for i in range(n):
        ts = bars.index[i]

        # 1. Fill any pending entry (decided from the *previous* bar's
        #    signal) at THIS bar's open — never the bar that produced the
        #    signal, which is the core no-lookahead guarantee.
        if pending is not None and position is None:
            raw_open = float(opens.iloc[i])
            slip = raw_open * (config.slippage_pct / 100.0)
            entry_price = raw_open + slip if pending.direction == "LONG" else raw_open - slip
            stop_price = (
                entry_price - pending.stop_distance
                if pending.direction == "LONG"
                else entry_price + pending.stop_distance
            )
            target_price = None
            if pending.target_distance is not None and not pd.isna(pending.target_distance):
                target_price = (
                    entry_price + pending.target_distance
                    if pending.direction == "LONG"
                    else entry_price - pending.target_distance
                )
            risk_amount = equity * (config.risk_pct_per_trade / 100.0)
            quantity = risk_amount / pending.stop_distance if pending.stop_distance > 0 else 0.0
            if quantity > 0:
                position = {
                    "direction": pending.direction,
                    "entry_time": ts,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "quantity": quantity,
                }
                day = ts.tz_convert(config.session_timezone).date()
                trades_today[day] = trades_today.get(day, 0) + 1
            pending = None

        # 2. Manage an open position using THIS bar's high/low (fair game
        #    once we're at/after the bar it was actually filled on).
        if position is not None:
            h, low = float(highs.iloc[i]), float(lows.iloc[i])
            exit_price: float | None = None
            exit_reason = ""
            if position["direction"] == "LONG":
                stop_hit = low <= position["stop_price"]
                target_hit = position["target_price"] is not None and h >= position["target_price"]
            else:
                stop_hit = h >= position["stop_price"]
                target_hit = (
                    position["target_price"] is not None and low <= position["target_price"]
                )

            if stop_hit and target_hit:
                # Conservative, documented assumption: when both are touched
                # within the same bar we cannot know which happened first
                # from OHLC alone, so the stop is assumed to have hit first.
                exit_price, exit_reason = (
                    position["stop_price"],
                    "STOP_TARGET_SAME_BAR_STOP_ASSUMED",
                )
            elif stop_hit:
                exit_price, exit_reason = position["stop_price"], "STOP"
            elif target_hit:
                exit_price, exit_reason = position["target_price"], "TARGET"
            elif _forced_close_due(ts, config):
                exit_price, exit_reason = float(closes.iloc[i]), "SESSION_CLOSE"
            elif i == n - 1:
                exit_price, exit_reason = float(closes.iloc[i]), "END_OF_DATA"

            if exit_price is not None:
                direction_sign = 1 if position["direction"] == "LONG" else -1
                gross_pnl = (
                    direction_sign * (exit_price - position["entry_price"]) * position["quantity"]
                )
                commission = (
                    config.commission_per_trade
                    + config.commission_pct
                    / 100.0
                    * (position["entry_price"] + exit_price)
                    * position["quantity"]
                )
                pnl = gross_pnl - commission
                equity += pnl
                risk_amount = (
                    abs(position["entry_price"] - position["stop_price"]) * position["quantity"]
                )
                r_multiple = pnl / risk_amount if risk_amount > 0 else 0.0
                result.trades.append(
                    Trade(
                        direction=position["direction"],
                        entry_time=position["entry_time"],
                        exit_time=ts,
                        entry_price=position["entry_price"],
                        exit_price=exit_price,
                        stop_price=position["stop_price"],
                        target_price=position["target_price"],
                        quantity=position["quantity"],
                        pnl=pnl,
                        pnl_pct=pnl / config.starting_balance * 100.0,
                        r_multiple=r_multiple,
                        exit_reason=exit_reason,
                    )
                )
                position = None

        # 3. Decide (not fill) a new entry from THIS bar's signal, to be
        #    filled at the NEXT bar's open — only if flat and not already
        #    holding a pending order, and only if a next bar exists.
        if position is None and pending is None and i + 1 < n:
            sig = signals.iloc[i]
            stop_distance = sig["stop_distance"]
            has_valid_stop = (
                stop_distance is not None and not pd.isna(stop_distance) and stop_distance > 0
            )
            day = ts.tz_convert(config.session_timezone).date()
            under_daily_cap = (
                config.max_trades_per_day is None
                or trades_today.get(day, 0) < config.max_trades_per_day
            )
            target_distance = sig["target_distance"]
            target_distance = None if pd.isna(target_distance) else float(target_distance)

            if bool(sig["long_entry"]) and config.allow_long and has_valid_stop and under_daily_cap:
                pending = _PendingEntry("LONG", float(stop_distance), target_distance)
            elif (
                bool(sig["short_entry"])
                and config.allow_short
                and has_valid_stop
                and under_daily_cap
            ):
                pending = _PendingEntry("SHORT", float(stop_distance), target_distance)

        unrealized = 0.0
        if position is not None:
            direction_sign = 1 if position["direction"] == "LONG" else -1
            unrealized = (
                direction_sign
                * (float(closes.iloc[i]) - position["entry_price"])
                * position["quantity"]
            )
        result.equity_curve.append((ts, equity + unrealized))

    if not bars.index.tz:
        result.warnings.append(
            "Input bars had no timezone — assumed UTC. Verify this matches your data source."
        )

    return result
