from __future__ import annotations

import numpy as np
import pandas as pd

from app.backtesting.engine import BacktestConfig, run_backtest
from app.backtesting.spec_evaluator import evaluate_condition, evaluate_spec_signals
from app.codegen.conditions import RECOGNIZED_CONDITION_TYPES, render_condition
from app.models.enums import RuleCategory
from app.strategy.compilable_rule import CompilableRule
from app.strategy.compiler import compile_strategy


def _bars(n=300, seed=4):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-02 09:00", periods=n, freq="5min", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 0.3, size=n))
    high = close + rng.uniform(0.05, 0.3, size=n)
    low = close - rng.uniform(0.05, 0.3, size=n)
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": 1000}, index=index
    )


def test_recognized_condition_types_are_handled_by_both_codegen_and_evaluator():
    df = _bars(60)
    for condition_type in RECOGNIZED_CONDITION_TYPES:
        mrr = {"type": condition_type, "length": 5}
        rendered = render_condition("some rule", mrr, ["1"])
        assert not rendered.is_placeholder, f"{condition_type} should render as real logic"

        series = evaluate_condition(df, mrr)
        assert isinstance(series, pd.Series)
        assert series.dtype == bool
        assert len(series) == len(df)


def test_unrecognized_condition_type_evaluates_to_always_false():
    df = _bars(20)
    series = evaluate_condition(df, {"type": "something_unknown"})
    assert not series.any()

    series_none = evaluate_condition(df, None)
    assert not series_none.any()


def test_full_pipeline_compile_evaluate_backtest_produces_trades():
    rules = [
        CompilableRule(
            id="1",
            category=RuleCategory.BIAS,
            natural_language_rule="Above 10 EMA",
            machine_readable_rule={"type": "price_above_ma", "length": 10, "direction": "long"},
        ),
        CompilableRule(
            id="2",
            category=RuleCategory.SETUP,
            natural_language_rule="always eligible",
            machine_readable_rule={"type": "always_true"},
        ),
        CompilableRule(
            id="3",
            category=RuleCategory.ENTRY,
            natural_language_rule="always eligible",
            machine_readable_rule={"type": "always_true"},
        ),
        CompilableRule(
            id="3b",
            category=RuleCategory.CONFIRMATION,
            natural_language_rule="always eligible",
            machine_readable_rule={"type": "always_true"},
        ),
        CompilableRule(
            id="4",
            category=RuleCategory.STOP_LOSS,
            natural_language_rule="1 point stop",
            machine_readable_rule={"method": "FIXED_POINTS", "value": 1.0},
        ),
        CompilableRule(
            id="5",
            category=RuleCategory.TAKE_PROFIT,
            natural_language_rule="2R",
            machine_readable_rule={"method": "R_MULTIPLE", "value": 2.0},
        ),
        CompilableRule(
            id="6",
            category=RuleCategory.POSITION_SIZING,
            natural_language_rule="1% risk",
            machine_readable_rule={"method": "RISK_PERCENT", "value": 1.0},
        ),
    ]
    spec = compile_strategy("Full Pipeline Test", rules)

    bars = _bars(500)
    signals = evaluate_spec_signals(spec, bars)
    result = run_backtest(
        bars, signals, BacktestConfig(starting_balance=10_000, risk_pct_per_trade=1.0)
    )

    assert len(result.trades) > 0
    for trade in result.trades:
        assert trade.quantity > 0
