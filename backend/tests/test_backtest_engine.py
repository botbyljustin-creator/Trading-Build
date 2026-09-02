from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.backtesting.engine import BacktestConfig, run_backtest


def _flat_bars(
    n: int, start_price: float = 100.0, start="2024-01-02 09:30", freq="5min"
) -> pd.DataFrame:
    """`n` bars that open/close at `start_price` with a small fixed range,
    so tests can deterministically place stop/target hits on specific bars."""
    index = pd.date_range(start=start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "open": [start_price] * n,
            "high": [start_price + 0.1] * n,
            "low": [start_price - 0.1] * n,
            "close": [start_price] * n,
            "volume": [1000] * n,
        },
        index=index,
    )


def _empty_signals(index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "long_entry": [False] * len(index),
            "short_entry": [False] * len(index),
            "stop_distance": [np.nan] * len(index),
            "target_distance": [np.nan] * len(index),
        },
        index=index,
    )


def test_entry_fills_at_next_bar_open_not_signal_bar_close():
    bars = _flat_bars(5)
    bars.loc[bars.index[2], "close"] = 999.0  # signal bar's own close must never be used as fill
    signals = _empty_signals(bars.index)
    signals.loc[bars.index[1], "long_entry"] = True
    signals.loc[bars.index[1], "stop_distance"] = 1.0

    result = run_backtest(bars, signals, BacktestConfig(starting_balance=10_000))
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_time == bars.index[2]
    assert trade.entry_price == pytest.approx(bars["open"].iloc[2])
    assert trade.entry_price != 999.0


def test_stop_loss_triggers_and_computes_expected_pnl():
    bars = _flat_bars(5, start_price=100.0)
    # Bar 2 (the fill bar) dips low enough to hit a 1.0-point stop.
    bars.loc[bars.index[2], "low"] = 98.5
    signals = _empty_signals(bars.index)
    signals.loc[bars.index[1], "long_entry"] = True
    signals.loc[bars.index[1], "stop_distance"] = 1.0

    config = BacktestConfig(starting_balance=10_000, risk_pct_per_trade=1.0)
    result = run_backtest(bars, signals, config)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "STOP"
    expected_quantity = (10_000 * 0.01) / 1.0
    assert trade.quantity == pytest.approx(expected_quantity)
    assert trade.exit_price == pytest.approx(trade.entry_price - 1.0)
    assert trade.pnl == pytest.approx(-1.0 * expected_quantity)


def test_take_profit_triggers_before_end_of_data():
    bars = _flat_bars(5, start_price=100.0)
    bars.loc[bars.index[2], "high"] = 104.0  # hits a 2R target (stop=1, target=2)
    signals = _empty_signals(bars.index)
    signals.loc[bars.index[1], "long_entry"] = True
    signals.loc[bars.index[1], "stop_distance"] = 1.0
    signals.loc[bars.index[1], "target_distance"] = 2.0

    result = run_backtest(bars, signals, BacktestConfig(starting_balance=10_000))
    trade = result.trades[0]
    assert trade.exit_reason == "TARGET"
    assert trade.r_multiple == pytest.approx(2.0, rel=1e-3)


def test_commission_and_slippage_reduce_pnl():
    bars = _flat_bars(6, start_price=100.0)
    bars.loc[bars.index[2], "high"] = 104.0
    signals = _empty_signals(bars.index)
    signals.loc[bars.index[1], "long_entry"] = True
    signals.loc[bars.index[1], "stop_distance"] = 1.0
    signals.loc[bars.index[1], "target_distance"] = 2.0

    no_cost = run_backtest(bars, signals, BacktestConfig(starting_balance=10_000))
    with_cost = run_backtest(
        bars,
        signals,
        BacktestConfig(starting_balance=10_000, commission_per_trade=5.0, slippage_pct=0.1),
    )
    assert (
        with_cost.trades[0].entry_price > no_cost.trades[0].entry_price
    )  # slippage on a long entry
    assert with_cost.trades[0].pnl < no_cost.trades[0].pnl  # commission + slippage both reduce pnl


def test_short_disabled_never_opens_a_short_position():
    bars = _flat_bars(5)
    signals = _empty_signals(bars.index)
    signals.loc[bars.index[1], "short_entry"] = True
    signals.loc[bars.index[1], "stop_distance"] = 1.0

    result = run_backtest(bars, signals, BacktestConfig(starting_balance=10_000, allow_short=False))
    assert result.trades == []


def test_max_trades_per_day_is_enforced():
    bars = _flat_bars(10)
    signals = _empty_signals(bars.index)
    # Signal every bar with a stop tight enough it never triggers early
    # (bar range is only +/-0.1, stop_distance is huge) so each position
    # rides to END_OF_DATA/next signal rather than stopping out early —
    # except we also need to be flat to open the next one, so use a target
    # instead that fires the same bar it fills to close out quickly.
    for idx in bars.index[:-1]:
        signals.loc[idx, "long_entry"] = True
        signals.loc[idx, "stop_distance"] = 50.0
        signals.loc[idx, "target_distance"] = 0.05

    result = run_backtest(
        bars, signals, BacktestConfig(starting_balance=10_000, max_trades_per_day=2)
    )
    assert len(result.trades) <= 2


def test_missing_stop_distance_is_never_traded():
    bars = _flat_bars(5)
    signals = _empty_signals(bars.index)
    signals.loc[bars.index[1], "long_entry"] = True
    # stop_distance left as NaN — the engine must never invent a stop.

    result = run_backtest(bars, signals, BacktestConfig(starting_balance=10_000))
    assert result.trades == []


def test_rejects_mismatched_indices():
    bars = _flat_bars(5)
    signals = _empty_signals(bars.index[:-1])
    with pytest.raises(ValueError):
        run_backtest(bars, signals, BacktestConfig(starting_balance=10_000))
