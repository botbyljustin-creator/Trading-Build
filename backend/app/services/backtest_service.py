"""Backtest orchestration (Modules 11-12): loads market data through the
`MarketDataProvider` abstraction, evaluates the compiled spec into signals,
runs the engine, and persists trades/metrics. Also generates
`assumptions_notes` so unrealistic or unresolved parts of the spec are
labeled on the result rather than silently backtested as if they were
fully defined.
"""

from __future__ import annotations

from datetime import time

from sqlalchemy.orm import Session

from app.backtesting.engine import BacktestConfig, run_backtest
from app.backtesting.metrics import compute_metrics
from app.backtesting.spec_evaluator import evaluate_spec_signals
from app.codegen.conditions import RECOGNIZED_CONDITION_TYPES
from app.data_providers.csv_provider import CSVMarketDataProvider
from app.models.backtest import Backtest, BacktestMetrics, BacktestTrade
from app.models.enums import BacktestStatus, TradeDirection
from app.models.strategy import StrategyVersion
from app.schemas.strategy_spec import StrategySpecification


def _condition_is_placeholder(condition: dict | None) -> bool:
    return not condition or condition.get("type") not in RECOGNIZED_CONDITION_TYPES


def _assumptions_notes(spec: StrategySpecification) -> list[str]:
    notes: list[str] = []
    for field_name, rule_text, condition in [
        ("bias", spec.bias_rule, spec.bias_condition),
        ("setup", spec.setup_rule, spec.setup_condition),
        ("confirmation", spec.confirmation_rule, spec.confirmation_condition),
        ("entry", spec.entry_rule, spec.entry_condition),
    ]:
        if rule_text and _condition_is_placeholder(condition):
            notes.append(
                f"The {field_name} rule ({rule_text!r}) could not be machine-translated and "
                "was treated as never-true in this backtest — results reflect that, not the "
                "creator's actual intended logic."
            )
        elif rule_text is None:
            notes.append(f"No {field_name} rule was compiled into this strategy version.")

    if spec.stop_loss and spec.stop_loss.method == "STRUCTURE_BASED":
        notes.append(
            "Stop-loss is structure-based text only; no numeric stop was applied in this backtest."
        )
    if spec.take_profit and spec.take_profit.method == "STRUCTURE_BASED":
        notes.append(
            "Take-profit is structure-based text only; no numeric target was applied in this backtest."
        )
    if spec.position_sizing is None:
        notes.append(
            "No position sizing rule was compiled — trades, if any, could not be sized and were skipped."
        )
    return notes


def run_backtest_for_version(
    db: Session, backtest: Backtest, version: StrategyVersion, csv_dir: str
) -> None:
    backtest.status = BacktestStatus.RUNNING
    db.commit()

    try:
        if version.spec is None:
            raise ValueError("Strategy version has no compiled specification.")
        spec = StrategySpecification.model_validate(version.spec.spec_json)

        if backtest.provider != "csv":
            raise ValueError(f"Unsupported market data provider: {backtest.provider}")
        provider = CSVMarketDataProvider(csv_dir)
        bars = provider.get_historical_bars(
            backtest.symbol, "raw", backtest.date_start, backtest.date_end
        )
        if bars.empty:
            raise ValueError(
                f"No bars found for symbol '{backtest.symbol}' in the requested date range."
            )

        signals = evaluate_spec_signals(spec, bars)

        session_end = None
        if spec.session is not None:
            h, m = spec.session.end_time.split(":")
            session_end = time(int(h), int(m))

        config = BacktestConfig(
            starting_balance=backtest.starting_balance,
            commission_per_trade=backtest.commission_per_trade,
            commission_pct=backtest.commission_pct,
            slippage_pct=backtest.slippage_pct,
            risk_pct_per_trade=backtest.risk_pct_per_trade,
            allow_long=backtest.allow_long and bool(spec.allow_long),
            allow_short=backtest.allow_short and bool(spec.allow_short),
            max_trades_per_day=backtest.max_trades_per_day,
            allow_overnight=spec.allow_overnight_positions is not False,
            session_end_time=session_end,
            session_timezone=backtest.timezone,
        )
        result = run_backtest(bars, signals, config)
        metrics = compute_metrics(result, backtest.starting_balance)

        for trade in result.trades:
            db.add(
                BacktestTrade(
                    backtest_id=backtest.id,
                    direction=TradeDirection(trade.direction),
                    entry_time=trade.entry_time,
                    exit_time=trade.exit_time,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    stop_price=trade.stop_price,
                    target_price=trade.target_price,
                    quantity=trade.quantity,
                    pnl=trade.pnl,
                    pnl_pct=trade.pnl_pct,
                    r_multiple=trade.r_multiple,
                    exit_reason=trade.exit_reason,
                )
            )

        db.add(
            BacktestMetrics(
                backtest_id=backtest.id,
                net_profit=metrics["net_profit"],
                total_return_pct=metrics["total_return_pct"],
                cagr_pct=metrics["cagr_pct"],
                max_drawdown_pct=metrics["max_drawdown_pct"],
                profit_factor=(
                    metrics["profit_factor"]
                    if isinstance(metrics["profit_factor"], int | float)
                    else None
                ),
                win_rate_pct=metrics["win_rate_pct"],
                avg_win=metrics["avg_win"],
                avg_loss=metrics["avg_loss"],
                win_loss_ratio=metrics["win_loss_ratio"],
                expectancy=metrics["expectancy"],
                sharpe_ratio=metrics["sharpe_ratio"],
                sortino_ratio=metrics["sortino_ratio"],
                num_trades=metrics["num_trades"],
                avg_trade=metrics["avg_trade"],
                largest_win=metrics["largest_win"],
                largest_loss=metrics["largest_loss"],
                max_consecutive_wins=metrics["max_consecutive_wins"],
                max_consecutive_losses=metrics["max_consecutive_losses"],
                avg_holding_period_minutes=metrics["avg_holding_period_minutes"],
                equity_curve=metrics["equity_curve"],
                drawdown_curve=metrics["drawdown_curve"],
                monthly_returns=metrics["monthly_returns"],
                long_stats=metrics["long_stats"],
                short_stats=metrics["short_stats"],
            )
        )

        notes = _assumptions_notes(spec)
        if result.warnings:
            notes.extend(result.warnings)
        backtest.assumptions_notes = "\n".join(notes) if notes else None
        backtest.status = BacktestStatus.COMPLETE
        db.commit()
    except Exception as exc:  # noqa: BLE001 — must persist failure, never crash the worker
        db.rollback()
        backtest.status = BacktestStatus.FAILED
        backtest.error_message = str(exc)
        db.commit()
        raise
