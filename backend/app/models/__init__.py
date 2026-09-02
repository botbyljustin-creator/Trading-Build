"""SQLAlchemy ORM models.

Every model module must be imported here so `Base.metadata` (used by
Alembic autogenerate) and the relationship string-references resolve
correctly, even though most callers should import a specific model from its
own module.
"""

from __future__ import annotations

from app.models.audit import AuditLog
from app.models.backtest import Backtest, BacktestMetrics, BacktestTrade, OptimizationRun
from app.models.base import Base
from app.models.concept import Concept, ConceptRelation, ConceptSource
from app.models.job import Job
from app.models.project import Project
from app.models.report import Report
from app.models.rule import Contradiction, Rule, RuleSource
from app.models.source import Embedding, Source, Transcript, TranscriptChunk, Video
from app.models.strategy import GeneratedCode, Strategy, StrategySpec, StrategyVersion
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Project",
    "Source",
    "Video",
    "Transcript",
    "TranscriptChunk",
    "Embedding",
    "Concept",
    "ConceptSource",
    "ConceptRelation",
    "Rule",
    "RuleSource",
    "Contradiction",
    "Strategy",
    "StrategyVersion",
    "StrategySpec",
    "GeneratedCode",
    "Backtest",
    "BacktestTrade",
    "BacktestMetrics",
    "OptimizationRun",
    "Report",
    "Job",
    "AuditLog",
]
