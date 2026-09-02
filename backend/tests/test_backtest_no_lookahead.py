"""Automated lookahead-bias detection (Module 12).

The core check is truncation invariance: everything the engine decides up
to time T can only depend on bars at or before T. So running the engine on
the full dataset and on a dataset truncated at T must produce byte-for-byte
identical trades/equity for the region strictly before T — if the engine
peeked at future bars to make an earlier decision, truncating the future
would change that earlier decision and this test would fail.

A small safety margin at the truncation boundary is excluded from
comparison, because the *last* bar of a truncated run is legitimately
treated differently (forced `END_OF_DATA` close) than the same bar in the
middle of the full run — that is expected, not lookahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.backtesting.engine import BacktestConfig, run_backtest

SAFETY_MARGIN_BARS = 5


def _synthetic_bars(n: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-02 09:30", periods=n, freq="5min", tz="UTC")
    steps = rng.normal(loc=0.0, scale=0.5, size=n)
    close = 100 + np.cumsum(steps)
    high = close + rng.uniform(0.1, 0.6, size=n)
    low = close - rng.uniform(0.1, 0.6, size=n)
    open_ = close + rng.normal(0, 0.1, size=n)
    volume = rng.integers(100, 1000, size=n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


def _synthetic_signals(bars: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(bars)
    long_entry = rng.random(n) < 0.15
    short_entry = (~long_entry) & (rng.random(n) < 0.15)
    return pd.DataFrame(
        {
            "long_entry": long_entry,
            "short_entry": short_entry,
            "stop_distance": np.full(n, 1.5),
            "target_distance": np.full(n, 3.0),
        },
        index=bars.index,
    )


@pytest.mark.parametrize("truncate_at", [80, 140, 190])
def test_results_before_truncation_point_are_identical(truncate_at: int):
    full_bars = _synthetic_bars(220)
    full_signals = _synthetic_signals(full_bars)
    config = BacktestConfig(starting_balance=10_000, risk_pct_per_trade=1.0)

    full_result = run_backtest(full_bars, full_signals, config)
    truncated_result = run_backtest(
        full_bars.iloc[:truncate_at], full_signals.iloc[:truncate_at], config
    )

    boundary_time = full_bars.index[truncate_at - SAFETY_MARGIN_BARS]

    full_trades_before = [t for t in full_result.trades if t.exit_time < boundary_time]
    truncated_trades_before = [t for t in truncated_result.trades if t.exit_time < boundary_time]

    assert len(full_trades_before) == len(truncated_trades_before)
    for a, b in zip(full_trades_before, truncated_trades_before, strict=True):
        assert a.entry_time == b.entry_time
        assert a.exit_time == b.exit_time
        assert a.entry_price == pytest.approx(b.entry_price)
        assert a.exit_price == pytest.approx(b.exit_price)
        assert a.pnl == pytest.approx(b.pnl)

    full_equity_before = {ts: eq for ts, eq in full_result.equity_curve if ts < boundary_time}
    truncated_equity_before = {
        ts: eq for ts, eq in truncated_result.equity_curve if ts < boundary_time
    }
    assert full_equity_before == pytest.approx(truncated_equity_before)


def test_replacing_future_bars_does_not_change_past_decisions():
    """A second, stronger variant: instead of truncating, overwrite every
    bar after T with completely different (randomized) data and confirm the
    trades/equity before T are unaffected."""
    bars = _synthetic_bars(150, seed=3)
    signals = _synthetic_signals(bars, seed=5)
    config = BacktestConfig(starting_balance=10_000)

    cutoff = 100
    mutated_bars = bars.copy()
    rng = np.random.default_rng(999)
    future_len = len(bars) - cutoff
    mutated_bars.iloc[
        cutoff:, mutated_bars.columns.get_indexer(["open", "high", "low", "close"])
    ] = rng.uniform(50, 500, size=(future_len, 4))

    baseline = run_backtest(bars, signals, config)
    mutated = run_backtest(mutated_bars, signals, config)

    boundary_time = bars.index[cutoff - SAFETY_MARGIN_BARS]
    baseline_before = [t for t in baseline.trades if t.exit_time < boundary_time]
    mutated_before = [t for t in mutated.trades if t.exit_time < boundary_time]

    assert len(baseline_before) == len(mutated_before)
    for a, b in zip(baseline_before, mutated_before, strict=True):
        assert a.pnl == pytest.approx(b.pnl)
        assert a.exit_price == pytest.approx(b.exit_price)
