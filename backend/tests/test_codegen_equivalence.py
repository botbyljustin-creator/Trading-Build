from __future__ import annotations

import ast

from app.codegen.pine import generate_pine_script
from app.codegen.python_gen import generate_python_strategy
from app.codegen.spec_embedding import extract_spec_json
from app.models.enums import RuleCategory
from app.strategy.compilable_rule import CompilableRule
from app.strategy.compiler import compile_strategy


def _sample_spec():
    rules = [
        CompilableRule(
            id="1", category=RuleCategory.MARKET, natural_language_rule="NASDAQ-100 proxy"
        ),
        CompilableRule(id="2", category=RuleCategory.TIMEFRAME, natural_language_rule="5 minute"),
        CompilableRule(
            id="3",
            category=RuleCategory.SESSION,
            natural_language_rule="9:30 to 11:30 New York",
            machine_readable_rule={
                "start_time": "09:30",
                "end_time": "11:30",
                "timezone": "America/New_York",
            },
        ),
        CompilableRule(
            id="4",
            category=RuleCategory.BIAS,
            natural_language_rule="Price above 200 EMA",
            machine_readable_rule={
                "type": "price_above_ma",
                "length": 200,
                "ma_type": "EMA",
                "direction": "long",
            },
        ),
        CompilableRule(
            id="5",
            category=RuleCategory.SETUP,
            natural_language_rule="Liquidity sweep below prior swing low",
        ),
        CompilableRule(
            id="6",
            category=RuleCategory.ENTRY,
            natural_language_rule="Close back above VWAP",
            machine_readable_rule={"type": "vwap_reclaim"},
        ),
        CompilableRule(
            id="7",
            category=RuleCategory.STOP_LOSS,
            natural_language_rule="Below the sweep low",
            machine_readable_rule={"method": "BELOW_SWING_LOW"},
        ),
        CompilableRule(
            id="8",
            category=RuleCategory.TAKE_PROFIT,
            natural_language_rule="2R",
            machine_readable_rule={"method": "R_MULTIPLE", "value": 2},
        ),
        CompilableRule(
            id="9",
            category=RuleCategory.POSITION_SIZING,
            natural_language_rule="0.5% of equity",
            machine_readable_rule={"method": "RISK_PERCENT", "value": 0.5, "max_trades_per_day": 2},
        ),
    ]
    return compile_strategy("Morning Reversal", rules)


def test_pine_and_python_embed_identical_spec():
    spec = _sample_spec()
    pine_code = generate_pine_script(spec, "v1")
    python_code = generate_python_strategy(spec, "v1")

    pine_spec = extract_spec_json(pine_code, "//")
    python_spec = extract_spec_json(python_code, "#")

    assert pine_spec == python_spec == spec.model_dump(mode="json")


def test_python_output_is_syntactically_valid():
    spec = _sample_spec()
    code = generate_python_strategy(spec, "v1")
    ast.parse(code)  # raises SyntaxError if invalid


def test_placeholder_conditions_never_silently_invent_logic():
    spec = _sample_spec()
    python_code = generate_python_strategy(spec, "v1")
    pine_code = generate_pine_script(spec, "v1")
    # SETUP had no machine-readable hint -> must render as an inert TODO,
    # not a fabricated condition, in both outputs.
    assert "TODO not yet machine-translatable" in python_code
    assert "TODO not yet machine-translatable" in pine_code
    assert "Liquidity sweep below prior swing low" in python_code


def test_recognized_condition_types_render_real_logic_in_both():
    spec = _sample_spec()
    python_code = generate_python_strategy(spec, "v1")
    pine_code = generate_pine_script(spec, "v1")
    assert "ema(close, 200)" in python_code
    assert "ta.ema(close, 200)" in pine_code
    assert "vwap" in python_code
    assert "vwapValue" in pine_code
