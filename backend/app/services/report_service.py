"""Reporting Agent (ARCHITECTURE.md §5.10): assembles the final strategy
report purely by templating already-validated structured data. No new
claims are generated at report time — narrative commentary, when included,
comes from the Backtest/Robustness Analyst agents' own (guardrailed)
output, passed in rather than generated here.
"""

from __future__ import annotations

from app.models.backtest import Backtest
from app.models.rule import Contradiction, Rule
from app.models.strategy import StrategyVersion
from app.schemas.analysis import BacktestAnalysis, RobustnessAnalysis
from app.schemas.strategy_spec import StrategySpecification
from app.strategy.completeness import check_completeness


def build_report(
    version: StrategyVersion,
    rules: list[Rule],
    contradictions: list[Contradiction],
    backtest: Backtest | None = None,
    backtest_analysis: BacktestAnalysis | None = None,
    robustness_analysis: RobustnessAnalysis | None = None,
) -> dict:
    spec = StrategySpecification.model_validate(version.spec.spec_json) if version.spec else None
    completeness = check_completeness(spec) if spec else None

    report: dict = {
        "strategy_summary": {
            "name": version.strategy.name if version.strategy else None,
            "version": version.label,
            "completeness_score_pct": completeness.score_pct if completeness else None,
        },
        "source_material": [
            {"video_id": str(v.video_id), "excerpt": v.excerpt} for r in rules for v in r.sources
        ][:50],
        "trading_philosophy": {
            "bias_rule": spec.bias_rule if spec else None,
            "market": spec.instrument.market_description if spec else None,
            "timeframe": spec.instrument.timeframe if spec else None,
        },
        "setup": spec.setup_rule if spec else None,
        "entry": {
            "confirmation": spec.confirmation_rule if spec else None,
            "entry_rule": spec.entry_rule if spec else None,
        },
        "exit": {
            "stop_loss": spec.stop_loss.model_dump() if spec and spec.stop_loss else None,
            "take_profit": spec.take_profit.model_dump() if spec and spec.take_profit else None,
        },
        "risk_management": (
            spec.position_sizing.model_dump() if spec and spec.position_sizing else None
        ),
        "trade_management": {
            "max_trades_per_day": spec.max_trades_per_day if spec else None,
            "allow_multiple_concurrent_positions": (
                spec.allow_multiple_concurrent_positions if spec else None
            ),
            "allow_overnight_positions": spec.allow_overnight_positions if spec else None,
            "notes": spec.trade_management_notes if spec else [],
        },
        "no_trade_conditions": spec.no_trade_conditions if spec else [],
        "rule_confidence": [
            {
                "rule_id": str(r.id),
                "category": r.category.value,
                "status": r.status.value,
                "confidence": r.confidence,
            }
            for r in rules
        ],
        "contradictions": [
            {
                "id": str(c.id),
                "explanation": c.explanation,
                "resolution": c.resolution.value,
                "rule_a_id": str(c.rule_a_id),
                "rule_b_id": str(c.rule_b_id),
            }
            for c in contradictions
        ],
        "missing_information": completeness.missing if completeness else [],
        "backtest_configuration": None,
        "backtest_results": None,
        "robustness_results": None,
        "limitations": [
            "This report describes a historical backtest of extracted educational "
            "content, not a live-trading recommendation. Past performance in a "
            "backtest does not indicate future results.",
        ],
        "strategy_version": version.version_number,
    }

    if backtest is not None:
        report["backtest_configuration"] = {
            "provider": backtest.provider,
            "symbol": backtest.symbol,
            "timezone": backtest.timezone,
            "asset_type": backtest.asset_type,
            "date_start": backtest.date_start.isoformat(),
            "date_end": backtest.date_end.isoformat(),
            "starting_balance": backtest.starting_balance,
            "commission_per_trade": backtest.commission_per_trade,
            "slippage_pct": backtest.slippage_pct,
            "risk_pct_per_trade": backtest.risk_pct_per_trade,
        }
        if backtest.metrics is not None:
            report["backtest_results"] = {
                "net_profit": backtest.metrics.net_profit,
                "total_return_pct": backtest.metrics.total_return_pct,
                "max_drawdown_pct": backtest.metrics.max_drawdown_pct,
                "profit_factor": backtest.metrics.profit_factor,
                "win_rate_pct": backtest.metrics.win_rate_pct,
                "sharpe_ratio": backtest.metrics.sharpe_ratio,
                "num_trades": backtest.metrics.num_trades,
            }
        if backtest.assumptions_notes:
            report["limitations"].append(backtest.assumptions_notes)

    if backtest_analysis is not None:
        report["backtest_results"] = {
            **(report["backtest_results"] or {}),
            "observations": backtest_analysis.observations,
            "caveats": backtest_analysis.caveats,
        }

    if robustness_analysis is not None:
        report["robustness_results"] = {
            "overfitting_risk": robustness_analysis.overfitting_risk,
            "reasons": robustness_analysis.reasons,
            "observations": robustness_analysis.observations,
        }

    return report
