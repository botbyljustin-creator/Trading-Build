"""Shared enums for StrategyForge AI domain models.

Plain `str, Enum` (not `PGEnum`) is used everywhere and persisted as
`sqlalchemy.Enum` with `native_enum=False` (VARCHAR + CHECK) so adding a new
member never requires an Alembic `ALTER TYPE` migration against Postgres
native enum types — only a new CHECK constraint migration, which is safer
to roll out incrementally.
"""

from __future__ import annotations

from enum import Enum


class SourceType(str, Enum):
    YOUTUBE_VIDEO = "YOUTUBE_VIDEO"
    YOUTUBE_PLAYLIST = "YOUTUBE_PLAYLIST"
    YOUTUBE_CHANNEL = "YOUTUBE_CHANNEL"


class SourceStatus(str, Enum):
    PENDING = "PENDING"
    RESOLVING = "RESOLVING"
    READY = "READY"
    FAILED = "FAILED"


class TranscriptStatus(str, Enum):
    PENDING = "PENDING"
    AVAILABLE = "AVAILABLE"
    TRANSCRIPT_UNAVAILABLE = "TRANSCRIPT_UNAVAILABLE"
    FAILED = "FAILED"


class RuleCategory(str, Enum):
    MARKET = "MARKET"
    TIMEFRAME = "TIMEFRAME"
    SESSION = "SESSION"
    MARKET_REGIME = "MARKET_REGIME"
    BIAS = "BIAS"
    SETUP = "SETUP"
    ENTRY = "ENTRY"
    CONFIRMATION = "CONFIRMATION"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    POSITION_SIZING = "POSITION_SIZING"
    TRADE_MANAGEMENT = "TRADE_MANAGEMENT"
    INVALIDATION = "INVALIDATION"
    NO_TRADE_CONDITIONS = "NO_TRADE_CONDITIONS"


class RuleStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    AMBIGUOUS = "AMBIGUOUS"
    CONTRADICTORY = "CONTRADICTORY"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_MODIFIED = "USER_MODIFIED"
    AI_ASSUMPTION = "AI_ASSUMPTION"
    REJECTED = "REJECTED"


# Rule statuses eligible for inclusion in a compiled StrategySpecification.
# Deliberately excludes AMBIGUOUS, CONTRADICTORY, AI_ASSUMPTION, REJECTED,
# and plain EXTRACTED (extraction alone is never enough — a human must
# confirm or modify it first).
COMPILABLE_RULE_STATUSES = frozenset({RuleStatus.USER_CONFIRMED, RuleStatus.USER_MODIFIED})


class ConceptRelationType(str, Enum):
    RELATED = "RELATED"
    CONFLICTING = "CONFLICTING"


class ContradictionResolution(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    USE_A = "USE_A"
    USE_B = "USE_B"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    KEEP_SEPARATE = "KEEP_SEPARATE"
    IGNORE = "IGNORE"


class RuleEvidenceType(str, Enum):
    """How directly the source material supports this rule — orthogonal to
    `RuleStatus` (which tracks review/compile-pipeline state, not evidence
    strength). Set once at extraction time; editing a rule's text doesn't
    change why it was originally classified this way."""

    EXPLICIT = "EXPLICIT"  # creator clearly states the rule
    IMPLIED = "IMPLIED"  # strongly implied by repeated examples, not stated outright
    DISCRETIONARY = "DISCRETIONARY"  # source explicitly frames this as requiring judgment
    USER_DEFINED = "USER_DEFINED"  # the user typed this rule directly, not extracted
    AI_ASSUMPTION = "AI_ASSUMPTION"  # the model inferred this to fill a gap; requires approval


class Quantifiability(str, Enum):
    FULLY_QUANTIFIABLE = "FULLY_QUANTIFIABLE"
    PARTIALLY_QUANTIFIABLE = "PARTIALLY_QUANTIFIABLE"
    DISCRETIONARY = "DISCRETIONARY"


class StrategyVersionStatus(str, Enum):
    DRAFT = "DRAFT"
    COMPILED = "COMPILED"
    ARCHIVED = "ARCHIVED"


class CodeLanguage(str, Enum):
    PINE = "PINE"
    PYTHON = "PYTHON"


class JobType(str, Enum):
    INGEST_SOURCE = "INGEST_SOURCE"
    FETCH_TRANSCRIPT = "FETCH_TRANSCRIPT"
    EXTRACT_CONCEPTS = "EXTRACT_CONCEPTS"
    EXTRACT_RULES = "EXTRACT_RULES"
    DETECT_CONTRADICTIONS = "DETECT_CONTRADICTIONS"
    COMPILE_STRATEGY = "COMPILE_STRATEGY"
    GENERATE_CODE = "GENERATE_CODE"
    RUN_BACKTEST = "RUN_BACKTEST"
    RUN_ROBUSTNESS = "RUN_ROBUSTNESS"
    GENERATE_REPORT = "GENERATE_REPORT"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class OverfittingRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class BacktestStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
