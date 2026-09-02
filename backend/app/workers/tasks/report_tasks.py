from __future__ import annotations

from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.models.backtest import Backtest
from app.models.job import Job
from app.models.report import Report
from app.models.rule import Contradiction, Rule
from app.models.strategy import StrategyVersion
from app.services import job_service
from app.services.report_service import build_report
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="reporting.generate_report")
def generate_report_task(job_id: str, strategy_version_id: str, backtest_id: str | None) -> None:
    from app.agents.backtest_analyst import analyze_backtest
    from app.agents.robustness_analyst import analyze_robustness
    from app.ai.factory import get_llm_provider

    db = get_session_factory()()
    try:
        job = db.get(Job, job_id)
        job_service.mark_running(db, job)
        try:
            version = db.get(StrategyVersion, strategy_version_id)
            rules = (
                db.query(Rule).filter(Rule.id.in_(version.rule_ids)).all()
                if version.rule_ids
                else []
            )
            contradictions = (
                db.query(Contradiction)
                .filter(Contradiction.project_id == version.strategy.project_id)
                .all()
            )
            backtest = db.get(Backtest, backtest_id) if backtest_id else None

            backtest_analysis = None
            robustness_analysis = None
            try:
                provider = get_llm_provider()
                if backtest is not None and backtest.metrics is not None:
                    backtest_analysis = analyze_backtest(
                        provider,
                        {
                            "net_profit": backtest.metrics.net_profit,
                            "win_rate_pct": backtest.metrics.win_rate_pct,
                            "profit_factor": backtest.metrics.profit_factor,
                            "num_trades": backtest.metrics.num_trades,
                            "max_drawdown_pct": backtest.metrics.max_drawdown_pct,
                            "long_stats": backtest.metrics.long_stats,
                            "short_stats": backtest.metrics.short_stats,
                        },
                    )
                if backtest is not None and backtest.optimization_runs:
                    latest = backtest.optimization_runs[-1]
                    robustness_analysis = analyze_robustness(
                        provider,
                        {
                            "overfitting_risk": (
                                latest.overfitting_risk.value if latest.overfitting_risk else None
                            ),
                            "reasons": latest.overfitting_reasons,
                            "results": latest.results,
                        },
                    )
            except (
                Exception
            ) as exc:  # noqa: BLE001 — analyst commentary is optional, not required for a report
                logger.warning("report_analyst_commentary_unavailable", error=str(exc))

            content = build_report(
                version, rules, contradictions, backtest, backtest_analysis, robustness_analysis
            )
            report = Report(
                strategy_version_id=version.id,
                backtest_id=backtest.id if backtest else None,
                content_json=content,
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            job_service.mark_success(db, job, result_ref={"report_id": str(report.id)})
        except Exception as exc:  # noqa: BLE001
            logger.error("generate_report_task_failed", job_id=job_id, error=str(exc))
            job_service.mark_failed(db, job, error_message=str(exc))
    finally:
        db.close()
