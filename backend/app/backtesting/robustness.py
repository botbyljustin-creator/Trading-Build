"""Robustness testing + overfitting protection (Modules 13-14).

Every function here is deterministic and independent of any LLM call — the
`RobustnessAnalyst` agent (`app/agents/robustness_analyst.py`) narrates
*these* outputs; it never computes the risk score itself, so a qualitative
model response can never override the numeric guardrail.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.backtesting.engine import BacktestConfig, Trade, run_backtest
from app.backtesting.metrics import compute_metrics


@dataclass(frozen=True)
class Split:
    train_bars: pd.DataFrame
    train_signals: pd.DataFrame
    test_bars: pd.DataFrame
    test_signals: pd.DataFrame
    split_index: int


def in_sample_out_of_sample_split(
    bars: pd.DataFrame, signals: pd.DataFrame, train_fraction: float = 0.7
) -> Split:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between 0 and 1 (exclusive).")
    split_index = int(len(bars) * train_fraction)
    return Split(
        train_bars=bars.iloc[:split_index],
        train_signals=signals.iloc[:split_index],
        test_bars=bars.iloc[split_index:],
        test_signals=signals.iloc[split_index:],
        split_index=split_index,
    )


def walk_forward_windows(
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    config: BacktestConfig,
    n_folds: int = 4,
    train_fraction: float = 0.7,
) -> list[dict]:
    """Rolling walk-forward: split the data into `n_folds` contiguous
    windows; within each window, train_fraction is in-sample and the rest
    is out-of-sample. Returns one metrics pair per fold."""
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")
    n = len(bars)
    fold_size = n // n_folds
    if fold_size < 10:
        raise ValueError("Not enough bars to run walk-forward with this many folds.")

    folds = []
    for fold_idx in range(n_folds):
        start = fold_idx * fold_size
        end = n if fold_idx == n_folds - 1 else (fold_idx + 1) * fold_size
        fold_bars = bars.iloc[start:end]
        fold_signals = signals.iloc[start:end]
        if len(fold_bars) < 10:
            continue
        split = in_sample_out_of_sample_split(fold_bars, fold_signals, train_fraction)
        in_sample = compute_metrics(
            run_backtest(split.train_bars, split.train_signals, config), config.starting_balance
        )
        out_sample = compute_metrics(
            run_backtest(split.test_bars, split.test_signals, config), config.starting_balance
        )
        folds.append(
            {
                "fold": fold_idx,
                "start": fold_bars.index[0].isoformat(),
                "end": fold_bars.index[-1].isoformat(),
                "in_sample": in_sample,
                "out_of_sample": out_sample,
            }
        )
    return folds


def parameter_sensitivity(
    bars: pd.DataFrame,
    config: BacktestConfig,
    signal_generator: Callable[..., pd.DataFrame],
    param_grid: dict[str, list],
) -> list[dict]:
    """`signal_generator(bars, **params) -> signals_df`. Runs every
    combination in `param_grid` (a full grid, not a search) and reports its
    metrics — the point is to see the shape of the response surface, not to
    pick the best combination (Module 13's stated goal)."""
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    results = []
    for combo in combos:
        params = dict(zip(keys, combo, strict=True))
        signals = signal_generator(bars, **params)
        metrics = compute_metrics(run_backtest(bars, signals, config), config.starting_balance)
        results.append({"params": params, "metrics": metrics})
    return results


def monte_carlo_trade_resequencing(
    trades: list[Trade], starting_balance: float, n_simulations: int = 1000, seed: int = 42
) -> dict:
    """Bootstraps the *order* trades occurred in (not their outcomes) to
    show how much of the reported equity curve/drawdown depends on the
    lucky/unlucky sequence in which wins and losses happened to land."""
    if len(trades) < 5:
        return {
            "n_simulations": 0,
            "note": "Fewer than 5 trades — Monte Carlo resequencing is not meaningful at this sample size.",
        }
    rng = np.random.default_rng(seed)
    pnls = np.array([t.pnl for t in trades])
    final_equities = np.empty(n_simulations)
    max_drawdowns = np.empty(n_simulations)

    for sim in range(n_simulations):
        order = rng.permutation(pnls)
        equity_path = starting_balance + np.cumsum(order)
        running_max = np.maximum.accumulate(np.concatenate(([starting_balance], equity_path)))[1:]
        drawdown = (equity_path - running_max) / running_max * 100.0
        final_equities[sim] = equity_path[-1]
        max_drawdowns[sim] = drawdown.min()

    return {
        "n_simulations": n_simulations,
        "final_equity_p5": float(np.percentile(final_equities, 5)),
        "final_equity_p50": float(np.percentile(final_equities, 50)),
        "final_equity_p95": float(np.percentile(final_equities, 95)),
        "max_drawdown_p5_pct": float(np.percentile(max_drawdowns, 5)),
        "max_drawdown_p50_pct": float(np.percentile(max_drawdowns, 50)),
        "worst_case_drawdown_pct": float(max_drawdowns.min()),
    }


@dataclass(frozen=True)
class OverfittingAssessment:
    risk: str  # LOW / MEDIUM / HIGH
    reasons: list[str]


def assess_overfitting_risk(
    *,
    parameters_optimized_count: int,
    combinations_tested_count: int,
    num_trades: int,
    in_sample_profit_factor: float | None = None,
    out_of_sample_profit_factor: float | None = None,
) -> OverfittingAssessment:
    """A deliberately simple, documented heuristic — not a statistical
    guarantee. Thresholds are conservative defaults meant to be tuned as
    real usage data comes in (see ROADMAP.md Phase 2)."""
    reasons: list[str] = []
    risk_rank = 0  # 0=LOW, 1=MEDIUM, 2=HIGH

    if parameters_optimized_count == 0:
        reasons.append("No parameters were optimized against this data.")
    else:
        trades_per_parameter = num_trades / parameters_optimized_count
        if trades_per_parameter < 20:
            risk_rank = max(risk_rank, 2)
            reasons.append(
                f"Only {trades_per_parameter:.1f} historical trades per optimized parameter "
                f"({num_trades} trades / {parameters_optimized_count} parameters) — a common rule "
                "of thumb wants several dozen at minimum."
            )
        elif trades_per_parameter < 50:
            risk_rank = max(risk_rank, 1)
            reasons.append(
                f"{trades_per_parameter:.1f} historical trades per optimized parameter is on the "
                "low side for confidence that results generalize."
            )

        if combinations_tested_count > 200:
            risk_rank = max(risk_rank, 2)
            reasons.append(
                f"{combinations_tested_count} parameter combinations were tested — a wide search increases the chance of finding a combination that fit noise."
            )
        elif combinations_tested_count > 50:
            risk_rank = max(risk_rank, 1)
            reasons.append(f"{combinations_tested_count} parameter combinations were tested.")

    if (
        in_sample_profit_factor is not None
        and out_of_sample_profit_factor is not None
        and in_sample_profit_factor > 0
    ):
        drop_pct = (
            (in_sample_profit_factor - out_of_sample_profit_factor)
            / in_sample_profit_factor
            * 100.0
        )
        if drop_pct > 50:
            risk_rank = max(risk_rank, 2)
            reasons.append(
                f"Out-of-sample profit factor is {drop_pct:.0f}% lower than in-sample "
                f"({in_sample_profit_factor:.2f} -> {out_of_sample_profit_factor:.2f})."
            )
        elif drop_pct > 25:
            risk_rank = max(risk_rank, 1)
            reasons.append(f"Out-of-sample profit factor is {drop_pct:.0f}% lower than in-sample.")

    if not reasons:
        reasons.append("No excessive optimization or in/out-of-sample degradation detected.")

    risk = ["LOW", "MEDIUM", "HIGH"][risk_rank]
    return OverfittingAssessment(risk=risk, reasons=reasons)
