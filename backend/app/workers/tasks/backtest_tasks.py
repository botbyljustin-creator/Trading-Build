from __future__ import annotations

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.models.backtest import Backtest
from app.models.job import Job
from app.models.strategy import StrategyVersion
from app.services import backtest_service, job_service
from app.services.audit import record_audit
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="backtesting.run_backtest")
def run_backtest_task(job_id: str, backtest_id: str) -> None:
    settings = get_settings()
    db = get_session_factory()()
    try:
        job = db.get(Job, job_id)
        backtest = db.get(Backtest, backtest_id)
        version = db.get(StrategyVersion, backtest.strategy_version_id)
        job_service.mark_running(db, job)
        try:
            backtest_service.run_backtest_for_version(
                db, backtest, version, settings.market_data_csv_dir
            )
            record_audit(
                db,
                project_id=version.strategy.project_id,
                user_id=None,
                action="backtest.performed",
                entity_type="Backtest",
                entity_id=backtest.id,
                details={"symbol": backtest.symbol, "status": backtest.status.value},
            )
            db.commit()
            job_service.mark_success(db, job, result_ref={"backtest_id": str(backtest.id)})
        except Exception as exc:  # noqa: BLE001
            logger.error("run_backtest_task_failed", job_id=job_id, error=str(exc))
            job_service.mark_failed(db, job, error_message=str(exc))
    finally:
        db.close()


@celery_app.task(name="backtesting.run_robustness")
def run_robustness_task(job_id: str, backtest_id: str) -> None:
    from app.backtesting.robustness import assess_overfitting_risk
    from app.models.backtest import OptimizationRun

    db = get_session_factory()()
    try:
        job = db.get(Job, job_id)
        backtest = db.get(Backtest, backtest_id)
        job_service.mark_running(db, job)
        try:
            trades = backtest.trades
            in_sample_count = len(trades) // 2
            in_sample = trades[:in_sample_count]
            out_sample = trades[in_sample_count:]

            def profit_factor(trade_set):
                wins = sum(t.pnl for t in trade_set if t.pnl > 0)
                losses = abs(sum(t.pnl for t in trade_set if t.pnl < 0))
                return (wins / losses) if losses > 0 else None

            in_pf = profit_factor(in_sample)
            out_pf = profit_factor(out_sample)
            assessment = assess_overfitting_risk(
                parameters_optimized_count=0,
                combinations_tested_count=0,
                num_trades=len(trades),
                in_sample_profit_factor=in_pf,
                out_of_sample_profit_factor=out_pf,
            )
            db.add(
                OptimizationRun(
                    backtest_id=backtest.id,
                    run_type="in_sample_out_of_sample",
                    params_tested={},
                    results={
                        "in_sample_profit_factor": in_pf,
                        "out_of_sample_profit_factor": out_pf,
                    },
                    parameters_optimized_count=0,
                    combinations_tested_count=0,
                    overfitting_risk=assessment.risk,
                    overfitting_reasons=assessment.reasons,
                )
            )
            db.commit()
            job_service.mark_success(db, job, result_ref={"overfitting_risk": assessment.risk})
        except Exception as exc:  # noqa: BLE001
            logger.error("run_robustness_task_failed", job_id=job_id, error=str(exc))
            job_service.mark_failed(db, job, error_message=str(exc))
    finally:
        db.close()
