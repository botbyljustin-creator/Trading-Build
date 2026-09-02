"""The `StrategySpecification` — the single machine-readable contract that
the Pine Script generator, the Python generator, and the backtest engine
all render from. Nothing about a real, tradeable strategy is invented here:
every populated field must trace back to one or more `USER_CONFIRMED` /
`USER_MODIFIED` rules (see `field_sources`), except fields the user typed
directly while filling a gap (`USER_PROVIDED`, tracked the same way but
without a rule id).

Any field left `None` means "the source material did not establish this."
The Strategy Auditor (`app/strategy/completeness.py`) turns that into an
explicit, visible gap — it never assumes a default.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

StopLossMethod = Literal[
    "FIXED_PRICE",
    "FIXED_POINTS",
    "FIXED_PERCENT",
    "ATR_MULTIPLE",
    "BELOW_SWING_LOW",
    "ABOVE_SWING_HIGH",
    "STRUCTURE_BASED",
]

TakeProfitMethod = Literal[
    "R_MULTIPLE",
    "FIXED_PRICE",
    "FIXED_POINTS",
    "FIXED_PERCENT",
    "ATR_MULTIPLE",
    "TRAILING",
    "STRUCTURE_BASED",
]

PositionSizingMethod = Literal["RISK_PERCENT", "FIXED_UNITS", "FIXED_NOTIONAL"]


class SessionWindow(BaseModel):
    start_time: str = Field(description="HH:MM, 24h, local to `timezone`.")
    end_time: str = Field(description="HH:MM, 24h, local to `timezone`.")
    timezone: str = Field(description="IANA timezone, e.g. 'America/New_York'.")
    days_of_week: list[int] = Field(
        default_factory=lambda: [0, 1, 2, 3, 4],
        description="0=Monday .. 6=Sunday. Defaults to weekdays only when a session is defined "
        "but the source did not specify which days.",
    )


class StopLossSpec(BaseModel):
    method: StopLossMethod
    value: float | None = Field(
        default=None, description="Numeric parameter for methods that need one (points/%/ATR mult)."
    )
    description: str


class TakeProfitSpec(BaseModel):
    method: TakeProfitMethod
    value: float | None = None
    description: str


class PositionSizingSpec(BaseModel):
    method: PositionSizingMethod
    value: float = Field(description="Risk % of equity, fixed unit count, or fixed notional.")
    description: str


class InstrumentBinding(BaseModel):
    """What market/instrument this strategy was described for. Deliberately
    separate from the backtest's own `provider`/`symbol` fields — a
    strategy can describe "NASDAQ-100" while a specific backtest run picks
    a concrete data source for it (see ARCHITECTURE.md §8)."""

    market_description: str | None = None
    timeframe: str | None = Field(default=None, description="e.g. '5m', '1h', '1D'.")


# Every field name below must correspond 1:1 with a key that can appear in
# `StrategySpecification.field_sources`, and with an entry in
# `app.strategy.completeness.REQUIRED_FIELDS`.
class StrategySpecification(BaseModel):
    strategy_name: str
    instrument: InstrumentBinding = Field(default_factory=InstrumentBinding)
    session: SessionWindow | None = None
    bias_rule: str | None = Field(default=None, description="How directional bias is determined.")
    bias_condition: dict | None = Field(
        default=None, description="Structured hint for code generation, if one rule provided it."
    )
    setup_rule: str | None = Field(default=None, description="What creates a valid setup.")
    setup_condition: dict | None = None
    confirmation_rule: str | None = None
    confirmation_condition: dict | None = None
    entry_rule: str | None = None
    entry_condition: dict | None = None
    stop_loss: StopLossSpec | None = None
    take_profit: TakeProfitSpec | None = None
    position_sizing: PositionSizingSpec | None = None
    max_trades_per_day: int | None = None
    allow_multiple_concurrent_positions: bool | None = None
    allow_overnight_positions: bool | None = None
    allow_long: bool | None = None
    allow_short: bool | None = None
    invalidation_rule: str | None = None
    no_trade_conditions: list[str] = Field(default_factory=list)
    trade_management_notes: list[str] = Field(default_factory=list)

    # field name -> list of rule IDs (as strings) that back it. A field with
    # a non-empty entry here that the user did not type directly is
    # traceable; the API surfaces this for the "click a source" requirement.
    field_sources: dict[str, list[str]] = Field(default_factory=dict)
    # field names the user typed directly during gap-filling rather than
    # having them extracted from a source.
    user_provided_fields: list[str] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=datetime.utcnow)
