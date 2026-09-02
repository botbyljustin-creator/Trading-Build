from __future__ import annotations

import pandas as pd

from app.backtesting.engine import BacktestResult, Trade
from app.backtesting.metrics import compute_metrics


def _trade(pnl, direction="LONG", entry="2024-01-02 09:30", exit_="2024-01-02 09:45"):
    entry_ts = pd.Timestamp(entry, tz="UTC")
    exit_ts = pd.Timestamp(exit_, tz="UTC")
    return Trade(
        direction=direction,
        entry_time=entry_ts,
        exit_time=exit_ts,
        entry_price=100.0,
        exit_price=100.0 + pnl,
        stop_price=99.0,
        target_price=102.0,
        quantity=1.0,
        pnl=pnl,
        pnl_pct=pnl,
        r_multiple=pnl,
        exit_reason="TARGET" if pnl > 0 else "STOP",
    )


def test_profit_factor_and_win_rate():
    trades = [_trade(10), _trade(10), _trade(-5)]
    equity_curve = [
        (pd.Timestamp("2024-01-02 09:30", tz="UTC"), 10_000),
        (pd.Timestamp("2024-01-02 09:45", tz="UTC"), 10_010),
        (pd.Timestamp("2024-01-02 10:00", tz="UTC"), 10_020),
        (pd.Timestamp("2024-01-02 10:15", tz="UTC"), 10_015),
    ]
    result = BacktestResult(trades=trades, equity_curve=equity_curve)
    metrics = compute_metrics(result, starting_balance=10_000)

    assert metrics["num_trades"] == 3
    assert metrics["net_profit"] == 15
    assert metrics["win_rate_pct"] == round(100 * 2 / 3, 2)
    assert metrics["profit_factor"] == 4.0  # 20 gross profit / 5 gross loss


def test_max_drawdown_is_negative_and_reflects_the_dip():
    equity_curve = [
        (pd.Timestamp("2024-01-02 09:30", tz="UTC"), 10_000),
        (pd.Timestamp("2024-01-02 09:45", tz="UTC"), 11_000),
        (pd.Timestamp("2024-01-02 10:00", tz="UTC"), 9_900),  # 10% drawdown from peak
        (pd.Timestamp("2024-01-02 10:15", tz="UTC"), 10_500),
    ]
    result = BacktestResult(trades=[], equity_curve=equity_curve)
    metrics = compute_metrics(result, starting_balance=10_000)
    assert metrics["max_drawdown_pct"] == pytest_approx(-10.0)


def pytest_approx(value, rel=1e-3):
    import pytest

    return pytest.approx(value, rel=rel)


def test_no_trades_returns_zeroed_metrics_not_an_error():
    result = BacktestResult(
        trades=[], equity_curve=[(pd.Timestamp("2024-01-02", tz="UTC"), 10_000)]
    )
    metrics = compute_metrics(result, starting_balance=10_000)
    assert metrics["num_trades"] == 0
    assert metrics["win_rate_pct"] == 0.0
    assert metrics["net_profit"] == 0
