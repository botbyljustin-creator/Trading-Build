from __future__ import annotations

from app.models.enums import RuleCategory
from app.strategy.compilable_rule import CompilableRule
from app.strategy.compiler import compile_strategy
from app.strategy.completeness import check_completeness
from app.strategy.versioning import diff_specs


def _rule(id_, category, text, mrr=None):
    return CompilableRule(
        id=id_, category=category, natural_language_rule=text, machine_readable_rule=mrr
    )


def test_compile_strategy_never_invents_missing_fields():
    rules = [
        _rule("1", RuleCategory.MARKET, "NASDAQ-100 proxy"),
        _rule("2", RuleCategory.ENTRY, "Enter on the next candle open"),
    ]
    spec = compile_strategy("Test Strategy", rules)

    assert spec.instrument.market_description == "NASDAQ-100 proxy."
    assert spec.entry_rule == "Enter on the next candle open."
    # Nothing was said about a stop, target, sizing, or session — these
    # must stay None, never a fabricated default.
    assert spec.stop_loss is None
    assert spec.take_profit is None
    assert spec.position_sizing is None
    assert spec.session is None
    assert spec.field_sources["instrument.market_description"] == ["1"]
    assert spec.field_sources["entry_rule"] == ["2"]


def test_stop_loss_uses_structured_hint_when_available():
    rules = [
        _rule(
            "1",
            RuleCategory.STOP_LOSS,
            "Stop 1.5 ATR below entry",
            mrr={"method": "ATR_MULTIPLE", "value": 1.5},
        )
    ]
    spec = compile_strategy("Test", rules)
    assert spec.stop_loss is not None
    assert spec.stop_loss.method == "ATR_MULTIPLE"
    assert spec.stop_loss.value == 1.5


def test_stop_loss_falls_back_to_structure_based_without_hint():
    rules = [_rule("1", RuleCategory.STOP_LOSS, "Stop below the sweep low")]
    spec = compile_strategy("Test", rules)
    assert spec.stop_loss is not None
    assert spec.stop_loss.method == "STRUCTURE_BASED"
    assert spec.stop_loss.value is None


def test_position_sizing_without_numeric_value_stays_missing():
    rules = [_rule("1", RuleCategory.POSITION_SIZING, "Risk a small amount per trade")]
    spec = compile_strategy("Test", rules)
    assert spec.position_sizing is None


def test_completeness_flags_every_missing_required_field():
    rules = [_rule("1", RuleCategory.MARKET, "NASDAQ-100 proxy")]
    spec = compile_strategy("Test", rules)
    report = check_completeness(spec)
    assert report.score_pct < 100
    assert "stop" in report.missing_keys
    assert "risk" in report.missing_keys
    assert "market" not in report.missing_keys


def test_completeness_full_strategy_scores_100():
    rules = [
        _rule("1", RuleCategory.MARKET, "NASDAQ-100 proxy"),
        _rule("2", RuleCategory.TIMEFRAME, "5 minute"),
        _rule(
            "3",
            RuleCategory.SESSION,
            "9:30 to 11:30 New York",
            mrr={"start_time": "09:30", "end_time": "11:30", "timezone": "America/New_York"},
        ),
        _rule("4", RuleCategory.BIAS, "Price above 200 EMA", mrr={"direction": "long"}),
        _rule("5", RuleCategory.SETUP, "Liquidity sweep below prior swing low"),
        _rule("6", RuleCategory.ENTRY, "Next candle open"),
        _rule(
            "7", RuleCategory.STOP_LOSS, "Below the sweep low", mrr={"method": "BELOW_SWING_LOW"}
        ),
        _rule("8", RuleCategory.TAKE_PROFIT, "2R", mrr={"method": "R_MULTIPLE", "value": 2}),
        _rule(
            "9",
            RuleCategory.POSITION_SIZING,
            "0.5% of equity",
            mrr={"method": "RISK_PERCENT", "value": 0.5, "max_trades_per_day": 2},
        ),
        _rule("10", RuleCategory.INVALIDATION, "Setup invalid if price closes back below the low"),
        _rule(
            "11",
            RuleCategory.TRADE_MANAGEMENT,
            "Only one position at a time, no overnight holds",
            mrr={"allow_multiple_concurrent_positions": False, "allow_overnight_positions": False},
        ),
    ]
    spec = compile_strategy("Complete Strategy", rules)
    report = check_completeness(spec)
    assert report.missing == []
    assert report.score_pct == 100.0
    assert spec.allow_long is True
    assert spec.allow_short is False
    assert spec.max_trades_per_day == 2


def test_diff_specs_reports_only_changed_fields():
    base_rules = [_rule("1", RuleCategory.ENTRY, "Enter at open")]
    v1 = compile_strategy("Test", base_rules)
    v2_rules = base_rules + [_rule("2", RuleCategory.STOP_LOSS, "Below swing low")]
    v2 = compile_strategy("Test", v2_rules)

    changes = diff_specs(v1, v2)
    assert "stop_loss" in changes
    assert changes["stop_loss"]["before"] is None
    assert "entry_rule" not in changes
