from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import BacktestStatus, OverfittingRisk, TradeDirection
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Backtest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One backtest run. Every field needed to reproduce the run exactly is
    stored here — nothing about "the market" is implicit (see
    ARCHITECTURE.md §8 on the US100/NAS100 instrument-identity problem)."""

    __tablename__ = "backtests"

    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategy_versions.id", ondelete="CASCADE"), index=True
    )
    # --- Instrument / data source identity (never assumed interchangeable) --
    provider: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(String(64))
    exchange_session: Mapped[str | None] = mapped_column(String(128), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(32))
    # --- Backtest configuration ---------------------------------------------
    date_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    date_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    starting_balance: Mapped[float] = mapped_column(Float)
    commission_per_trade: Mapped[float] = mapped_column(Float, default=0.0)
    commission_pct: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_pct: Mapped[float] = mapped_column(Float, default=0.0)
    risk_pct_per_trade: Mapped[float] = mapped_column(Float)
    position_sizing_method: Mapped[str] = mapped_column(String(32), default="risk_pct")
    allow_long: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_short: Mapped[bool] = mapped_column(Boolean, default=True)
    max_trades_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[BacktestStatus] = mapped_column(
        SAEnum(BacktestStatus, native_enum=False, length=16), default=BacktestStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assumptions_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Auto-generated notes on unrealistic/simplifying assumptions in this run.",
    )

    strategy_version: Mapped[StrategyVersion] = relationship(  # noqa: F821
        back_populates="backtests"
    )
    trades: Mapped[list[BacktestTrade]] = relationship(
        back_populates="backtest", cascade="all, delete-orphan", order_by="BacktestTrade.entry_time"
    )
    metrics: Mapped[BacktestMetrics | None] = relationship(
        back_populates="backtest", uselist=False, cascade="all, delete-orphan"
    )
    optimization_runs: Mapped[list[OptimizationRun]] = relationship(
        back_populates="backtest", cascade="all, delete-orphan"
    )


class BacktestTrade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "backtest_trades"

    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtests.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[TradeDirection] = mapped_column(
        SAEnum(TradeDirection, native_enum=False, length=8)
    )
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float)
    pnl_pct: Mapped[float] = mapped_column(Float)
    r_multiple: Mapped[float] = mapped_column(Float)
    exit_reason: Mapped[str] = mapped_column(String(64))

    backtest: Mapped[Backtest] = relationship(back_populates="trades")


class BacktestMetrics(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "backtest_metrics"

    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtests.id", ondelete="CASCADE"), unique=True, index=True
    )
    net_profit: Mapped[float] = mapped_column(Float)
    total_return_pct: Mapped[float] = mapped_column(Float)
    cagr_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate_pct: Mapped[float] = mapped_column(Float)
    avg_win: Mapped[float] = mapped_column(Float)
    avg_loss: Mapped[float] = mapped_column(Float)
    win_loss_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectancy: Mapped[float] = mapped_column(Float)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_trades: Mapped[int] = mapped_column(Integer)
    avg_trade: Mapped[float] = mapped_column(Float)
    largest_win: Mapped[float] = mapped_column(Float)
    largest_loss: Mapped[float] = mapped_column(Float)
    max_consecutive_wins: Mapped[int] = mapped_column(Integer)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer)
    avg_holding_period_minutes: Mapped[float] = mapped_column(Float)
    equity_curve: Mapped[list] = mapped_column(JSONB)
    drawdown_curve: Mapped[list] = mapped_column(JSONB)
    monthly_returns: Mapped[dict] = mapped_column(JSONB)
    long_stats: Mapped[dict] = mapped_column(JSONB)
    short_stats: Mapped[dict] = mapped_column(JSONB)

    backtest: Mapped[Backtest] = relationship(back_populates="metrics")


class OptimizationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Robustness-testing output (Modules 13-14): walk-forward, sensitivity,
    Monte Carlo, and the resulting overfitting-risk assessment."""

    __tablename__ = "optimization_runs"

    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtests.id", ondelete="CASCADE"), index=True
    )
    run_type: Mapped[str] = mapped_column(String(32))
    params_tested: Mapped[dict] = mapped_column(JSONB)
    results: Mapped[dict] = mapped_column(JSONB)
    parameters_optimized_count: Mapped[int] = mapped_column(Integer, default=0)
    combinations_tested_count: Mapped[int] = mapped_column(Integer, default=0)
    in_sample_vs_out_sample_delta_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    overfitting_risk: Mapped[OverfittingRisk | None] = mapped_column(
        SAEnum(OverfittingRisk, native_enum=False, length=16), nullable=True
    )
    overfitting_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    backtest: Mapped[Backtest] = relationship(back_populates="optimization_runs")
