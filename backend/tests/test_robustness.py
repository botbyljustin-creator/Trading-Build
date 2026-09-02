from __future__ import annotations

import numpy as np
import pandas as pd

from app.backtesting.engine import BacktestConfig, Trade
from app.backtesting.robustness import (
    assess_overfitting_risk,
    in_sample_out_of_sample_split,
    monte_carlo_trade_resequencing,
    walk_forward_windows,
)


def _synthetic_bars(n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-02 09:30", periods=n, freq="5min", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close + rng.uniform(0.1, 0.6, size=n)
    low = close - rng.uniform(0.1, 0.6, size=n)
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": 500}, index=index
    )


def _synthetic_signals(bars: pd.DataFrame, seed: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(bars)
    return pd.DataFrame(
        {
            "long_entry": rng.random(n) < 0.2,
            "short_entry": False,
            "stop_distance": 1.0,
            "target_distance": 2.0,
        },
        index=bars.index,
    )


def test_in_sample_out_of_sample_split_sizes():
    bars = _synthetic_bars(100)
    signals = _synthetic_signals(bars)
    split = in_sample_out_of_sample_split(bars, signals, train_fraction=0.7)
    assert len(split.train_bars) == 70
    assert len(split.test_bars) == 30
    assert split.train_bars.index[-1] < split.test_bars.index[0]


def test_walk_forward_windows_produce_metrics_per_fold():
    bars = _synthetic_bars(400)
    signals = _synthetic_signals(bars)
    config = BacktestConfig(starting_balance=10_000)
    folds = walk_forward_windows(bars, signals, config, n_folds=4)
    assert len(folds) == 4
    for fold in folds:
        assert "in_sample" in fold and "out_of_sample" in fold
        assert "net_profit" in fold["in_sample"]


def test_monte_carlo_resequencing_reflects_sequence_risk():
    trades = [
        Trade(
            direction="LONG",
            entry_time=pd.Timestamp("2024-01-02", tz="UTC"),
            exit_time=pd.Timestamp("2024-01-02", tz="UTC"),
            entry_price=100,
            exit_price=100 + pnl,
            stop_price=99,
            target_price=102,
            quantity=1,
            pnl=pnl,
            pnl_pct=pnl,
            r_multiple=pnl,
            exit_reason="TARGET" if pnl > 0 else "STOP",
        )
        for pnl in [50, 50, 50, -100, -100, 30, -20, 40, -10, 60]
    ]
    result = monte_carlo_trade_resequencing(trades, starting_balance=10_000, n_simulations=500)
    assert result["n_simulations"] == 500
    assert result["final_equity_p5"] <= result["final_equity_p50"] <= result["final_equity_p95"]
    assert result["worst_case_drawdown_pct"] <= result["max_drawdown_p5_pct"]


def test_monte_carlo_declines_with_too_few_trades():
    result = monte_carlo_trade_resequencing([], starting_balance=10_000)
    assert result["n_simulations"] == 0


def test_overfitting_risk_low_when_nothing_optimized():
    assessment = assess_overfitting_risk(
        parameters_optimized_count=0, combinations_tested_count=0, num_trades=40
    )
    assert assessment.risk == "LOW"


def test_overfitting_risk_high_with_many_params_and_few_trades():
    assessment = assess_overfitting_risk(
        parameters_optimized_count=10, combinations_tested_count=500, num_trades=30
    )
    assert assessment.risk == "HIGH"


def test_overfitting_risk_high_on_severe_out_of_sample_degradation():
    assessment = assess_overfitting_risk(
        parameters_optimized_count=1,
        combinations_tested_count=5,
        num_trades=1000,
        in_sample_profit_factor=3.0,
        out_of_sample_profit_factor=1.0,
    )
    assert assessment.risk == "HIGH"
    assert any("profit factor" in r for r in assessment.reasons)
