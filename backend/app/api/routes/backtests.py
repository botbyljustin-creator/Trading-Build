from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.routes.common import JobOut
from app.core.db import get_db
from app.models.backtest import Backtest, OptimizationRun
from app.models.enums import BacktestStatus, JobType, OverfittingRisk, TradeDirection
from app.models.strategy import StrategyVersion
from app.models.user import User
from app.security.clerk import get_current_user
from app.security.ownership import get_owned_backtest, get_owned_strategy_version
from app.services import job_service
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1", tags=["backtests"])


class BacktestCreate(BaseModel):
    provider: str = Field(default="csv")
    symbol: str
    timezone: str
    exchange_session: str | None = None
    asset_type: str
    date_start: datetime
    date_end: datetime
    starting_balance: float = Field(gt=0)
    commission_per_trade: float = 0.0
    commission_pct: float = 0.0
    slippage_pct: float = 0.0
    risk_pct_per_trade: float = Field(gt=0)
    allow_long: bool = True
    allow_short: bool = True
    max_trades_per_day: int | None = None


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    direction: TradeDirection
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float | None
    quantity: float
    pnl: float
    pnl_pct: float
    r_multiple: float
    exit_reason: str


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    net_profit: float
    total_return_pct: float
    cagr_pct: float | None
    max_drawdown_pct: float
    profit_factor: float | None
    win_rate_pct: float
    avg_win: float
    avg_loss: float
    win_loss_ratio: float | None
    expectancy: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    num_trades: int
    avg_trade: float
    largest_win: float
    largest_loss: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_holding_period_minutes: float
    equity_curve: list
    drawdown_curve: list
    monthly_returns: dict
    long_stats: dict
    short_stats: dict


class BacktestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    strategy_version_id: uuid.UUID
    provider: str
    symbol: str
    timezone: str
    asset_type: str
    date_start: datetime
    date_end: datetime
    starting_balance: float
    status: BacktestStatus
    error_message: str | None
    assumptions_notes: str | None
    created_at: datetime
    metrics: MetricsOut | None
    trades: list[TradeOut]


class OptimizationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_type: str
    results: dict
    overfitting_risk: OverfittingRisk | None
    overfitting_reasons: list | None


@router.post(
    "/strategy-versions/{version_id}/backtests",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_backtest(
    payload: BacktestCreate,
    version: StrategyVersion = Depends(get_owned_strategy_version),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    backtest = Backtest(
        strategy_version_id=version.id,
        provider=payload.provider,
        symbol=payload.symbol,
        timezone=payload.timezone,
        exchange_session=payload.exchange_session,
        asset_type=payload.asset_type,
        date_start=payload.date_start,
        date_end=payload.date_end,
        starting_balance=payload.starting_balance,
        commission_per_trade=payload.commission_per_trade,
        commission_pct=payload.commission_pct,
        slippage_pct=payload.slippage_pct,
        risk_pct_per_trade=payload.risk_pct_per_trade,
        allow_long=payload.allow_long,
        allow_short=payload.allow_short,
        max_trades_per_day=payload.max_trades_per_day,
    )
    db.add(backtest)
    db.flush()
    record_audit(
        db,
        project_id=version.strategy.project_id,
        user_id=user.id,
        action="backtest.started",
        entity_type="Backtest",
        entity_id=backtest.id,
        details={"symbol": payload.symbol, "provider": payload.provider},
    )
    db.commit()
    db.refresh(backtest)

    job = job_service.create_job(
        db,
        project_id=version.strategy.project_id,
        job_type=JobType.RUN_BACKTEST,
        input_ref={"backtest_id": str(backtest.id)},
    )
    from app.workers.tasks.backtest_tasks import run_backtest_task

    run_backtest_task.delay(str(job.id), str(backtest.id))
    db.refresh(job)
    return job


@router.get("/strategy-versions/{version_id}/backtests", response_model=list[BacktestOut])
def list_backtests(
    version: StrategyVersion = Depends(get_owned_strategy_version), db: Session = Depends(get_db)
) -> list[Backtest]:
    return (
        db.query(Backtest)
        .filter(Backtest.strategy_version_id == version.id)
        .order_by(Backtest.created_at.desc())
        .all()
    )


@router.get("/backtests/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest: Backtest = Depends(get_owned_backtest)) -> Backtest:
    return backtest


@router.post(
    "/backtests/{backtest_id}/robustness",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_robustness(
    backtest: Backtest = Depends(get_owned_backtest),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    if backtest.status != BacktestStatus.COMPLETE:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409, detail="Backtest must be COMPLETE before running robustness tests."
        )
    strategy_version = backtest.strategy_version
    job = job_service.create_job(
        db,
        project_id=strategy_version.strategy.project_id,
        job_type=JobType.RUN_ROBUSTNESS,
        input_ref={"backtest_id": str(backtest.id)},
    )
    from app.workers.tasks.backtest_tasks import run_robustness_task

    run_robustness_task.delay(str(job.id), str(backtest.id))
    db.refresh(job)
    return job


@router.get("/backtests/{backtest_id}/robustness", response_model=list[OptimizationRunOut])
def list_robustness_runs(
    backtest: Backtest = Depends(get_owned_backtest), db: Session = Depends(get_db)
) -> list[OptimizationRun]:
    return db.query(OptimizationRun).filter(OptimizationRun.backtest_id == backtest.id).all()
