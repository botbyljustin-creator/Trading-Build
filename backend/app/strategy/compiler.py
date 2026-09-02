"""Strategy Architect (deterministic — ARCHITECTURE.md §5.5).

Combines rules the caller has already filtered to `USER_CONFIRMED` /
`USER_MODIFIED` status into a `StrategySpecification`. This module never
queries rule status itself — `compile_strategy` trusts its caller to have
applied `COMPILABLE_RULE_STATUSES` (`app/services/strategy_service.py` does
this against the database) — but it also never fabricates a field value it
cannot derive from a rule; anything it can't confidently parse is left
`None` so the Strategy Auditor (`completeness.py`) surfaces it as missing
rather than the compiler silently guessing.
"""

from __future__ import annotations

from collections import defaultdict

from app.models.enums import RuleCategory
from app.schemas.strategy_spec import (
    InstrumentBinding,
    PositionSizingSpec,
    SessionWindow,
    StopLossSpec,
    StrategySpecification,
    TakeProfitSpec,
)
from app.strategy.compilable_rule import CompilableRule


def _by_category(rules: list[CompilableRule]) -> dict[RuleCategory, list[CompilableRule]]:
    grouped: dict[RuleCategory, list[CompilableRule]] = defaultdict(list)
    for rule in rules:
        grouped[rule.category].append(rule)
    return grouped


def _join_text(rules: list[CompilableRule]) -> str:
    return " ".join(r.natural_language_rule.strip().rstrip(".") + "." for r in rules)


def _record_sources(
    field_sources: dict[str, list[str]], field: str, rules: list[CompilableRule]
) -> None:
    if rules:
        field_sources[field] = [r.id for r in rules]


def _first_condition_hint(rules: list[CompilableRule]) -> dict | None:
    """The first rule in the group carrying a recognized `type` hint in its
    `machine_readable_rule`, for use by the code generators' condition
    registry (`app/codegen/conditions.py`)."""
    for rule in rules:
        if rule.machine_readable_rule and "type" in rule.machine_readable_rule:
            return rule.machine_readable_rule
    return None


def _build_session(rules: list[CompilableRule]) -> SessionWindow | None:
    for rule in rules:
        mrr = rule.machine_readable_rule or {}
        start = mrr.get("start_time")
        end = mrr.get("end_time")
        tz = mrr.get("timezone")
        if start and end and tz:
            return SessionWindow(
                start_time=str(start),
                end_time=str(end),
                timezone=str(tz),
                days_of_week=mrr.get("days_of_week", [0, 1, 2, 3, 4]),
            )
    return None


def _build_stop_loss(rules: list[CompilableRule]) -> StopLossSpec | None:
    if not rules:
        return None
    for rule in rules:
        mrr = rule.machine_readable_rule or {}
        method = mrr.get("method")
        if method:
            return StopLossSpec(
                method=method, value=mrr.get("value"), description=rule.natural_language_rule
            )
    # No rule had a parseable structured method — fall back to a
    # description-only, structure-based stop rather than inventing a number.
    return StopLossSpec(method="STRUCTURE_BASED", value=None, description=_join_text(rules))


def _build_take_profit(rules: list[CompilableRule]) -> TakeProfitSpec | None:
    if not rules:
        return None
    for rule in rules:
        mrr = rule.machine_readable_rule or {}
        method = mrr.get("method")
        if method:
            return TakeProfitSpec(
                method=method, value=mrr.get("value"), description=rule.natural_language_rule
            )
    return TakeProfitSpec(method="STRUCTURE_BASED", value=None, description=_join_text(rules))


def _build_position_sizing(rules: list[CompilableRule]) -> PositionSizingSpec | None:
    for rule in rules:
        mrr = rule.machine_readable_rule or {}
        method = mrr.get("method")
        value = mrr.get("value")
        if method and value is not None:
            return PositionSizingSpec(
                method=method, value=float(value), description=rule.natural_language_rule
            )
    # A POSITION_SIZING rule exists but had no parseable numeric value — do
    # not invent a risk percentage; leave it missing for the user to define.
    return None


def _find_flag(rules: list[CompilableRule], key: str) -> bool | None:
    for rule in rules:
        mrr = rule.machine_readable_rule or {}
        if key in mrr:
            return bool(mrr[key])
    return None


def _find_int(rules: list[CompilableRule], key: str) -> int | None:
    for rule in rules:
        mrr = rule.machine_readable_rule or {}
        if key in mrr:
            try:
                return int(mrr[key])
            except (TypeError, ValueError):
                continue
    return None


def _derive_direction_permissions(
    all_rules: list[CompilableRule],
) -> tuple[bool | None, bool | None]:
    directions: set[str] = set()
    for rule in all_rules:
        mrr = rule.machine_readable_rule or {}
        direction = mrr.get("direction")
        if isinstance(direction, str):
            directions.add(direction.lower())
    if not directions:
        return None, None
    allow_long = "long" in directions or "both" in directions
    allow_short = "short" in directions or "both" in directions
    return allow_long, allow_short


def compile_strategy(
    strategy_name: str, compilable_rules: list[CompilableRule]
) -> StrategySpecification:
    grouped = _by_category(compilable_rules)
    field_sources: dict[str, list[str]] = {}

    market_rules = grouped.get(RuleCategory.MARKET, [])
    timeframe_rules = grouped.get(RuleCategory.TIMEFRAME, [])
    session_rules = grouped.get(RuleCategory.SESSION, [])
    bias_rules = grouped.get(RuleCategory.BIAS, []) + grouped.get(RuleCategory.MARKET_REGIME, [])
    setup_rules = grouped.get(RuleCategory.SETUP, [])
    entry_rules = grouped.get(RuleCategory.ENTRY, [])
    confirmation_rules = grouped.get(RuleCategory.CONFIRMATION, [])
    stop_rules = grouped.get(RuleCategory.STOP_LOSS, [])
    target_rules = grouped.get(RuleCategory.TAKE_PROFIT, [])
    sizing_rules = grouped.get(RuleCategory.POSITION_SIZING, [])
    trade_mgmt_rules = grouped.get(RuleCategory.TRADE_MANAGEMENT, [])
    invalidation_rules = grouped.get(RuleCategory.INVALIDATION, [])
    no_trade_rules = grouped.get(RuleCategory.NO_TRADE_CONDITIONS, [])

    instrument = InstrumentBinding(
        market_description=_join_text(market_rules) or None,
        timeframe=_join_text(timeframe_rules) or None,
    )
    session = _build_session(session_rules)
    bias_rule = _join_text(bias_rules) or None
    setup_rule = _join_text(setup_rules) or None
    entry_rule = _join_text(entry_rules) or None
    confirmation_rule = _join_text(confirmation_rules) or None
    stop_loss = _build_stop_loss(stop_rules)
    take_profit = _build_take_profit(target_rules)
    position_sizing = _build_position_sizing(sizing_rules)
    invalidation_rule = _join_text(invalidation_rules) or None
    no_trade_conditions = [r.natural_language_rule for r in no_trade_rules]
    trade_management_notes = [r.natural_language_rule for r in trade_mgmt_rules]

    allow_long, allow_short = _derive_direction_permissions(compilable_rules)
    max_trades_per_day = _find_int(sizing_rules + trade_mgmt_rules, "max_trades_per_day")
    allow_multiple = _find_flag(trade_mgmt_rules, "allow_multiple_concurrent_positions")
    allow_overnight = _find_flag(trade_mgmt_rules, "allow_overnight_positions")

    if market_rules:
        field_sources["instrument.market_description"] = [r.id for r in market_rules]
    if timeframe_rules:
        field_sources["instrument.timeframe"] = [r.id for r in timeframe_rules]
    _record_sources(field_sources, "session", session_rules)
    _record_sources(field_sources, "bias_rule", bias_rules)
    _record_sources(field_sources, "setup_rule", setup_rules)
    _record_sources(field_sources, "entry_rule", entry_rules)
    _record_sources(field_sources, "confirmation_rule", confirmation_rules)
    _record_sources(field_sources, "stop_loss", stop_rules)
    _record_sources(field_sources, "take_profit", target_rules)
    if position_sizing is not None:
        _record_sources(field_sources, "position_sizing", sizing_rules)
    _record_sources(field_sources, "invalidation_rule", invalidation_rules)
    _record_sources(field_sources, "no_trade_conditions", no_trade_rules)
    _record_sources(field_sources, "trade_management_notes", trade_mgmt_rules)

    return StrategySpecification(
        strategy_name=strategy_name,
        instrument=instrument,
        session=session,
        bias_rule=bias_rule,
        bias_condition=_first_condition_hint(bias_rules),
        setup_rule=setup_rule,
        setup_condition=_first_condition_hint(setup_rules),
        confirmation_rule=confirmation_rule,
        confirmation_condition=_first_condition_hint(confirmation_rules),
        entry_rule=entry_rule,
        entry_condition=_first_condition_hint(entry_rules),
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_sizing=position_sizing,
        max_trades_per_day=max_trades_per_day,
        allow_multiple_concurrent_positions=allow_multiple,
        allow_overnight_positions=allow_overnight,
        allow_long=allow_long,
        allow_short=allow_short,
        invalidation_rule=invalidation_rule,
        no_trade_conditions=no_trade_conditions,
        trade_management_notes=trade_management_notes,
        field_sources=field_sources,
    )
