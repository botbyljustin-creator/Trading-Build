"""Backtest performance metrics (Module 11).

Pure functions over a `BacktestResult` — no I/O, fully unit-testable with
synthetic trade lists.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.backtesting.engine import BacktestResult, Trade


def _max_drawdown_pct(equity_curve: list[tuple[pd.Timestamp, float]]) -> tuple[float, list[dict]]:
    if not equity_curve:
        return 0.0, []
    values = pd.Series([v for _, v in equity_curve], index=[t for t, _ in equity_curve])
    running_max = values.cummax()
    drawdown = (values - running_max) / running_max.replace(0, np.nan) * 100.0
    drawdown = drawdown.fillna(0.0)
    curve = [
        {"timestamp": ts.isoformat(), "drawdown_pct": float(dd)} for ts, dd in drawdown.items()
    ]
    return float(drawdown.min()), curve


def _monthly_returns(equity_curve: list[tuple[pd.Timestamp, float]]) -> dict[str, float]:
    if not equity_curve:
        return {}
    series = pd.Series([v for _, v in equity_curve], index=[t for t, _ in equity_curve])
    monthly_last = series.resample("ME").last().dropna()
    returns = {}
    prev_value = series.iloc[0]
    for period, last_value in monthly_last.items():
        pct = (last_value - prev_value) / prev_value * 100.0 if prev_value else 0.0
        returns[period.strftime("%Y-%m")] = round(float(pct), 4)
        prev_value = last_value
    return returns


def _consecutive_counts(trades: list[Trade]) -> tuple[int, int]:
    max_wins = max_losses = cur_wins = cur_losses = 0
    for t in trades:
        if t.pnl > 0:
            cur_wins += 1
            cur_losses = 0
        elif t.pnl < 0:
            cur_losses += 1
            cur_wins = 0
        else:
            cur_wins = cur_losses = 0
        max_wins = max(max_wins, cur_wins)
        max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses


def _direction_stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"num_trades": 0, "win_rate_pct": 0.0, "net_profit": 0.0}
    wins = [t for t in trades if t.pnl > 0]
    return {
        "num_trades": len(trades),
        "win_rate_pct": round(100.0 * len(wins) / len(trades), 2),
        "net_profit": round(sum(t.pnl for t in trades), 2),
    }


def compute_metrics(
    result: BacktestResult, starting_balance: float, risk_free_rate_pct: float = 0.0
) -> dict:
    trades = result.trades
    equity_curve = result.equity_curve

    net_profit = sum(t.pnl for t in trades)
    ending_equity = equity_curve[-1][1] if equity_curve else starting_balance
    total_return_pct = (
        (ending_equity - starting_balance) / starting_balance * 100.0 if starting_balance else 0.0
    )

    cagr_pct = None
    if equity_curve and len(equity_curve) > 1:
        days = (equity_curve[-1][0] - equity_curve[0][0]).total_seconds() / 86400.0
        years = days / 365.25
        if years > 0 and starting_balance > 0 and ending_equity > 0:
            cagr_pct = (((ending_equity / starting_balance) ** (1 / years)) - 1) * 100.0

    max_dd_pct, drawdown_curve = _max_drawdown_pct(equity_curve)

    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (
        (gross_profit / gross_loss) if gross_loss > 0 else (None if not wins else math.inf)
    )
    win_rate_pct = 100.0 * len(wins) / len(trades) if trades else 0.0
    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    win_loss_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else None
    expectancy = (net_profit / len(trades)) if trades else 0.0

    # Sharpe/Sortino computed on the per-trade return series (simplest,
    # sample-size-appropriate measure for a discretionary-rules strategy
    # with a modest trade count — documented as a limitation, not a
    # continuous daily-return Sharpe, in BACKTESTING.md).
    trade_returns = np.array([t.pnl_pct for t in trades]) if trades else np.array([])
    sharpe_ratio = None
    sortino_ratio = None
    if len(trade_returns) > 1 and trade_returns.std(ddof=1) > 0:
        sharpe_ratio = float(
            (trade_returns.mean() - risk_free_rate_pct) / trade_returns.std(ddof=1)
        )
        downside = trade_returns[trade_returns < 0]
        if len(downside) > 1 and downside.std(ddof=1) > 0:
            sortino_ratio = float(
                (trade_returns.mean() - risk_free_rate_pct) / downside.std(ddof=1)
            )

    max_consecutive_wins, max_consecutive_losses = _consecutive_counts(trades)
    holding_minutes = [(t.exit_time - t.entry_time).total_seconds() / 60.0 for t in trades]
    avg_holding_period_minutes = float(np.mean(holding_minutes)) if holding_minutes else 0.0

    long_trades = [t for t in trades if t.direction == "LONG"]
    short_trades = [t for t in trades if t.direction == "SHORT"]

    return {
        "net_profit": round(net_profit, 2),
        "total_return_pct": round(total_return_pct, 4),
        "cagr_pct": round(cagr_pct, 4) if cagr_pct is not None else None,
        "max_drawdown_pct": round(max_dd_pct, 4),
        "profit_factor": (
            round(profit_factor, 4)
            if isinstance(profit_factor, float) and math.isfinite(profit_factor)
            else profit_factor
        ),
        "win_rate_pct": round(win_rate_pct, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "win_loss_ratio": round(win_loss_ratio, 4) if win_loss_ratio is not None else None,
        "expectancy": round(expectancy, 2),
        "sharpe_ratio": round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
        "sortino_ratio": round(sortino_ratio, 4) if sortino_ratio is not None else None,
        "num_trades": len(trades),
        "avg_trade": round(expectancy, 2),
        "largest_win": round(max(wins), 2) if wins else 0.0,
        "largest_loss": round(min(losses), 2) if losses else 0.0,
        "max_consecutive_wins": max_consecutive_wins,
        "max_consecutive_losses": max_consecutive_losses,
        "avg_holding_period_minutes": round(avg_holding_period_minutes, 2),
        "equity_curve": [
            {"timestamp": ts.isoformat(), "equity": round(v, 2)} for ts, v in equity_curve
        ],
        "drawdown_curve": drawdown_curve,
        "monthly_returns": _monthly_returns(equity_curve),
        "long_stats": _direction_stats(long_trades),
        "short_stats": _direction_stats(short_trades),
    }
