"""Strategy versioning helpers (Module 8).

Version rows themselves live in the database (`StrategyVersion`); this
module only contains the pure diffing logic used to render a
version-to-version comparison, so it can be unit-tested without a database.
"""

from __future__ import annotations

from app.schemas.strategy_spec import StrategySpecification

# Top-level fields compared verbatim. Nested objects (session, stop_loss,
# take_profit, position_sizing) are compared by their serialized form so any
# change inside them shows up as a change to that one field.
_COMPARABLE_FIELDS = [
    "instrument",
    "session",
    "bias_rule",
    "setup_rule",
    "confirmation_rule",
    "entry_rule",
    "stop_loss",
    "take_profit",
    "position_sizing",
    "max_trades_per_day",
    "allow_multiple_concurrent_positions",
    "allow_overnight_positions",
    "allow_long",
    "allow_short",
    "invalidation_rule",
    "no_trade_conditions",
    "trade_management_notes",
]


def diff_specs(old: StrategySpecification | None, new: StrategySpecification) -> dict[str, dict]:
    """Return {field: {"before": ..., "after": ...}} for every field that
    changed between two spec versions. `old=None` means every populated
    field in `new` is reported as newly added."""
    changes: dict[str, dict] = {}
    old_dump = old.model_dump(mode="json") if old else {}
    new_dump = new.model_dump(mode="json")
    for field in _COMPARABLE_FIELDS:
        before = old_dump.get(field)
        after = new_dump.get(field)
        if before != after:
            changes[field] = {"before": before, "after": after}
    return changes
