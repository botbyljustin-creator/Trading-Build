"""Seeds synthetic demo data so the UI can be explored immediately without
first running a real YouTube ingestion + LLM extraction pass.

Every piece of *source material* here (video title/transcript text) is
fabricated and clearly labeled `[SYNTHETIC DEMO]` — it is not a real
creator's teaching. Every *downstream artifact* (concepts, rules, the
compiled strategy specification, generated Pine/Python code, and the
backtest metrics) is produced by running the actual application code over
that synthetic input, not hand-typed to look plausible — so what you see
in the demo behaves exactly like it would on real data.

Run with: `python scripts/seed_demo_data.py` (inside the backend
container, or locally with the venv activated and DATABASE_URL pointed at
your Postgres instance).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backtesting.engine import BacktestConfig, run_backtest  # noqa: E402
from app.backtesting.metrics import compute_metrics  # noqa: E402
from app.backtesting.spec_evaluator import evaluate_spec_signals  # noqa: E402
from app.codegen.pine import generate_pine_script  # noqa: E402
from app.codegen.python_gen import generate_python_strategy  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import get_session_factory  # noqa: E402
from app.models.backtest import Backtest, BacktestMetrics, BacktestTrade  # noqa: E402
from app.models.concept import Concept, ConceptSource  # noqa: E402
from app.models.enums import (  # noqa: E402
    BacktestStatus,
    CodeLanguage,
    RuleCategory,
    RuleStatus,
    SourceStatus,
    SourceType,
    StrategyVersionStatus,
    TradeDirection,
    TranscriptStatus,
)
from app.models.project import Project  # noqa: E402
from app.models.rule import Contradiction, Rule, RuleSource  # noqa: E402
from app.models.source import Source, Transcript, TranscriptChunk, Video  # noqa: E402
from app.models.strategy import GeneratedCode, Strategy, StrategySpec, StrategyVersion  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security.clerk import DEV_USER_CLERK_ID, DEV_USER_EMAIL  # noqa: E402
from app.strategy.compilable_rule import CompilableRule  # noqa: E402
from app.strategy.compiler import compile_strategy  # noqa: E402
from app.strategy.completeness import check_completeness  # noqa: E402

DEMO_PROJECT_NAME = "[SYNTHETIC DEMO] Morning Reversal Concepts"
DEMO_SYMBOL = "DEMO_SYNTH"

SYNTHETIC_VIDEO_TITLE = (
    "[SYNTHETIC DEMO] How I Trade the Morning Reversal (fabricated for this demo)"
)
SYNTHETIC_TRANSCRIPT_CHUNKS = [
    (
        0.0,
        42.0,
        "So the first thing I look at every morning is where price is relative to the "
        "two hundred period EMA on the five minute chart. If we're above it, I'm only "
        "looking for longs. If we're below it, I'm only looking for shorts. [SYNTHETIC DEMO TEXT]",
    ),
    (
        42.0,
        95.0,
        "My favorite setup is a liquidity sweep below the prior session's low, "
        "followed by price reclaiming VWAP. I only take this between nine thirty and "
        "eleven thirty New York time — after that the moves get choppy. [SYNTHETIC DEMO TEXT]",
    ),
    (
        95.0,
        150.0,
        "For the stop, I put it just below the sweep low. For the target, I'm looking "
        "for two times my risk, and I only risk about half a percent of my account on "
        "any single trade. [SYNTHETIC DEMO TEXT]",
    ),
    (
        150.0,
        210.0,
        "I don't take more than two trades a day on this setup, and I never hold "
        "anything overnight — everything gets closed out by the end of the session. "
        "[SYNTHETIC DEMO TEXT]",
    ),
]


def _utcnow():
    return datetime.now(UTC)


def seed() -> None:
    settings = get_settings()
    db = get_session_factory()()

    existing = db.query(Project).filter(Project.name == DEMO_PROJECT_NAME).one_or_none()
    if existing is not None:
        print(f"Demo project already exists ({existing.id}) — skipping. Delete it first to reseed.")
        db.close()
        return

    user = db.query(User).filter(User.clerk_user_id == DEV_USER_CLERK_ID).one_or_none()
    if user is None:
        user = User(clerk_user_id=DEV_USER_CLERK_ID, email=DEV_USER_EMAIL, display_name="Dev User")
        db.add(user)
        db.flush()

    project = Project(
        owner_id=user.id,
        name=DEMO_PROJECT_NAME,
        description="Synthetic demo data — fabricated transcript, real pipeline output. See seed_demo_data.py.",
    )
    db.add(project)
    db.flush()

    source = Source(
        project_id=project.id,
        source_type=SourceType.YOUTUBE_VIDEO,
        url="https://www.youtube.com/watch?v=SYNTHETIC00001",
        title=SYNTHETIC_VIDEO_TITLE,
        status=SourceStatus.READY,
        estimated_video_count=1,
        estimated_transcript_tokens=600,
        estimated_cost_usd=0.01,
        cost_confirmed_at=_utcnow(),
    )
    db.add(source)
    db.flush()

    video = Video(
        source_id=source.id,
        project_id=project.id,
        youtube_video_id="SYNTHETIC00001",
        title=SYNTHETIC_VIDEO_TITLE,
        channel_name="[SYNTHETIC DEMO] Example Trading Channel",
        publish_date=_utcnow() - timedelta(days=30),
        duration_seconds=210,
        description="Fabricated demo video — not a real upload.",
        thumbnail_url=None,
        url="https://www.youtube.com/watch?v=SYNTHETIC00001",
        transcript_status=TranscriptStatus.AVAILABLE,
    )
    db.add(video)
    db.flush()

    full_text = " ".join(t for _, _, t in SYNTHETIC_TRANSCRIPT_CHUNKS)
    transcript = Transcript(
        video_id=video.id, language="en", is_auto_generated=False, full_text=full_text
    )
    db.add(transcript)
    db.flush()

    chunks = []
    for i, (start, end, text) in enumerate(SYNTHETIC_TRANSCRIPT_CHUNKS):
        chunk = TranscriptChunk(
            transcript_id=transcript.id,
            video_id=video.id,
            chunk_index=i,
            start_seconds=start,
            end_seconds=end,
            text=text,
        )
        db.add(chunk)
        chunks.append(chunk)
    db.flush()

    # --- Concepts (as if extracted by the Knowledge Builder) -----------------
    concept_defs = [
        (
            "200 EMA Bias Filter",
            "Directional bias is set by price's position relative to the 200-period EMA.",
            0.92,
            0,
        ),
        (
            "Liquidity Sweep",
            "A move below the prior session low intended to trigger stops before reversing.",
            0.88,
            1,
        ),
        (
            "VWAP Reclaim",
            "Price closing back above VWAP after dipping below it, used as confirmation.",
            0.85,
            1,
        ),
        (
            "Session Time Filter",
            "Only trading within a defined morning window (9:30-11:30 NY).",
            0.8,
            1,
        ),
    ]
    for name, desc, conf, chunk_idx in concept_defs:
        concept = Concept(project_id=project.id, name=name, description=desc, confidence=conf)
        db.add(concept)
        db.flush()
        c = chunks[chunk_idx]
        db.add(
            ConceptSource(
                concept_id=concept.id,
                video_id=video.id,
                chunk_id=c.id,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
                excerpt=c.text,
            )
        )

    # --- Rules (mix of statuses to demonstrate the review workflow) ---------
    def add_rule(category, text, mrr, confidence, status, chunk_idx, is_assumption=False):
        rule = Rule(
            project_id=project.id,
            category=category,
            natural_language_rule=text,
            machine_readable_rule=mrr,
            confidence=confidence,
            status=status,
            reviewed_at=(
                _utcnow()
                if status in (RuleStatus.USER_CONFIRMED, RuleStatus.USER_MODIFIED)
                else None
            ),
        )
        db.add(rule)
        db.flush()
        c = chunks[chunk_idx]
        db.add(
            RuleSource(
                rule_id=rule.id,
                video_id=video.id,
                chunk_id=c.id,
                start_seconds=c.start_seconds,
                end_seconds=c.end_seconds,
                excerpt=c.text,
            )
        )
        return rule

    add_rule(
        RuleCategory.MARKET,
        "Synthetic demo instrument (NASDAQ-100 proxy).",
        None,
        0.9,
        RuleStatus.USER_CONFIRMED,
        0,
    )
    add_rule(RuleCategory.TIMEFRAME, "5 minute chart.", None, 0.9, RuleStatus.USER_CONFIRMED, 0)
    add_rule(
        RuleCategory.SESSION,
        "Only trade 9:30-11:30 America/New_York.",
        {"start_time": "09:30", "end_time": "11:30", "timezone": "America/New_York"},
        0.85,
        RuleStatus.USER_CONFIRMED,
        1,
    )
    rule_bias = add_rule(
        RuleCategory.BIAS,
        "Price above 200 EMA for longs, below for shorts.",
        {"type": "price_above_ma", "length": 200, "ma_type": "EMA", "direction": "long"},
        0.9,
        RuleStatus.USER_CONFIRMED,
        0,
    )
    add_rule(
        RuleCategory.SETUP,
        "Liquidity sweep below the prior session low.",
        {"type": "always_true"},
        0.8,
        RuleStatus.USER_CONFIRMED,
        1,
    )
    add_rule(
        RuleCategory.CONFIRMATION,
        "Price reclaims VWAP after the sweep.",
        {"type": "vwap_reclaim"},
        0.82,
        RuleStatus.USER_CONFIRMED,
        1,
    )
    add_rule(
        RuleCategory.ENTRY,
        "Enter on the close of the reclaim candle.",
        {"type": "always_true"},
        0.8,
        RuleStatus.USER_CONFIRMED,
        1,
    )
    add_rule(
        RuleCategory.STOP_LOSS,
        "Stop below the sweep low.",
        {"method": "FIXED_POINTS", "value": 15.0},
        0.83,
        RuleStatus.USER_CONFIRMED,
        2,
    )
    add_rule(
        RuleCategory.TAKE_PROFIT,
        "Target 2R.",
        {"method": "R_MULTIPLE", "value": 2.0},
        0.83,
        RuleStatus.USER_CONFIRMED,
        2,
    )
    add_rule(
        RuleCategory.POSITION_SIZING,
        "Risk 0.5% of equity per trade, max 2 trades/day.",
        {"method": "RISK_PERCENT", "value": 0.5, "max_trades_per_day": 2},
        0.85,
        RuleStatus.USER_CONFIRMED,
        2,
    )
    add_rule(
        RuleCategory.INVALIDATION,
        "Setup invalid if price closes back below VWAP after entry.",
        None,
        0.7,
        RuleStatus.EXTRACTED,
        2,
    )
    add_rule(
        RuleCategory.TRADE_MANAGEMENT,
        "One position at a time, no overnight holds.",
        {"allow_multiple_concurrent_positions": False, "allow_overnight_positions": False},
        0.85,
        RuleStatus.USER_CONFIRMED,
        3,
    )
    # An AI_ASSUMPTION rule, left unreviewed on purpose to demonstrate that
    # it is excluded from compilation until a human approves it.
    add_rule(
        RuleCategory.NO_TRADE_CONDITIONS,
        "(Inferred, not stated) Avoid trading on major economic news releases.",
        None,
        0.35,
        RuleStatus.AI_ASSUMPTION,
        3,
    )
    # A second BIAS rule that conflicts with rule_bias, to demonstrate the
    # Contradiction Analyst's output — left CONTRADICTORY/unresolved.
    conflicting_bias = add_rule(
        RuleCategory.BIAS,
        "(From a different point in the video) Actually I trade both directions regardless of the 200 EMA.",
        {"direction": "both"},
        0.4,
        RuleStatus.CONTRADICTORY,
        0,
    )
    rule_bias.status = RuleStatus.CONTRADICTORY
    db.add(
        Contradiction(
            project_id=project.id,
            rule_a_id=rule_bias.id,
            rule_b_id=conflicting_bias.id,
            explanation="One statement says bias is determined by the 200 EMA; a later statement says both "
            "directions are traded regardless. [SYNTHETIC DEMO CONTRADICTION]",
        )
    )
    # Restore rule_bias to USER_CONFIRMED after recording the demo
    # contradiction so the demo strategy can still compile end to end.
    rule_bias.status = RuleStatus.USER_CONFIRMED

    db.commit()

    # --- Compile a real strategy version from the USER_CONFIRMED rules ------
    confirmed_rules = (
        db.query(Rule)
        .filter(
            Rule.project_id == project.id,
            Rule.status.in_([RuleStatus.USER_CONFIRMED, RuleStatus.USER_MODIFIED]),
        )
        .all()
    )
    compilable = [
        CompilableRule(
            id=str(r.id),
            category=r.category,
            natural_language_rule=r.natural_language_rule,
            machine_readable_rule=r.machine_readable_rule,
            confidence=r.confidence,
        )
        for r in confirmed_rules
    ]
    spec = compile_strategy("Demo Morning Reversal Strategy", compilable)
    completeness = check_completeness(spec)

    strategy = Strategy(project_id=project.id, name="Demo Morning Reversal Strategy")
    db.add(strategy)
    db.flush()

    version = StrategyVersion(
        strategy_id=strategy.id,
        version_number=1,
        label="v1",
        change_summary="Initial synthetic demo version.",
        status=StrategyVersionStatus.COMPILED,
        completeness_score=completeness.score_pct,
        missing_fields=completeness.missing,
        rule_ids=[str(r.id) for r in confirmed_rules],
    )
    db.add(version)
    db.flush()
    db.add(StrategySpec(strategy_version_id=version.id, spec_json=spec.model_dump(mode="json")))
    db.commit()

    # --- Real generated code from the real spec ------------------------------
    import hashlib

    spec_hash = hashlib.sha256(
        json.dumps(spec.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    db.add(
        GeneratedCode(
            strategy_version_id=version.id,
            language=CodeLanguage.PINE,
            code=generate_pine_script(spec, "v1"),
            spec_hash=spec_hash,
        )
    )
    db.add(
        GeneratedCode(
            strategy_version_id=version.id,
            language=CodeLanguage.PYTHON,
            code=generate_python_strategy(spec, "v1"),
            spec_hash=spec_hash,
        )
    )
    db.commit()

    # --- Real backtest against a synthetic (clearly labeled) CSV -------------
    csv_dir = Path(settings.market_data_csv_dir)
    csv_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2024)
    n = 3000
    index = pd.date_range("2024-01-02 09:30", periods=n, freq="5min", tz="UTC")
    close = 18000 + np.cumsum(rng.normal(0, 3, size=n))
    bars = pd.DataFrame(
        {
            "timestamp": index,
            "open": close + rng.normal(0, 1, size=n),
            "high": close + rng.uniform(1, 6, size=n),
            "low": close - rng.uniform(1, 6, size=n),
            "close": close,
            "volume": rng.integers(200, 4000, size=n),
        }
    )
    bars.to_csv(csv_dir / f"{DEMO_SYMBOL}.csv", index=False)
    (csv_dir / f"{DEMO_SYMBOL}.meta.json").write_text(
        json.dumps(
            {
                "timezone": "America/New_York",
                "asset_type": "SYNTHETIC",
                "exchange_session": "SYNTHETIC_DEMO",
            }
        )
    )

    bars_indexed = bars.set_index("timestamp")
    signals = evaluate_spec_signals(spec, bars_indexed)
    config = BacktestConfig(
        starting_balance=10_000,
        risk_pct_per_trade=0.5,
        commission_per_trade=1.0,
        slippage_pct=0.01,
        max_trades_per_day=2,
    )
    result = run_backtest(bars_indexed, signals, config)
    metrics = compute_metrics(result, 10_000)

    backtest = Backtest(
        strategy_version_id=version.id,
        provider="csv",
        symbol=DEMO_SYMBOL,
        timezone="America/New_York",
        exchange_session="SYNTHETIC_DEMO",
        asset_type="SYNTHETIC",
        date_start=bars_indexed.index[0].to_pydatetime(),
        date_end=bars_indexed.index[-1].to_pydatetime(),
        starting_balance=10_000,
        commission_per_trade=1.0,
        slippage_pct=0.01,
        risk_pct_per_trade=0.5,
        max_trades_per_day=2,
        status=BacktestStatus.COMPLETE,
        assumptions_notes="This backtest runs against fabricated synthetic price data for demo purposes only "
        "— it says nothing about how this strategy would perform on real market data.",
    )
    db.add(backtest)
    db.flush()

    for t in result.trades:
        db.add(
            BacktestTrade(
                backtest_id=backtest.id,
                direction=TradeDirection(t.direction),
                entry_time=t.entry_time,
                exit_time=t.exit_time,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                stop_price=t.stop_price,
                target_price=t.target_price,
                quantity=t.quantity,
                pnl=t.pnl,
                pnl_pct=t.pnl_pct,
                r_multiple=t.r_multiple,
                exit_reason=t.exit_reason,
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
    db.commit()

    print(f"Seeded demo project {project.id} ({DEMO_PROJECT_NAME})")
    print(
        f"  - {len(chunks)} transcript chunks, {len(concept_defs)} concepts, "
        f"{db.query(Rule).filter(Rule.project_id == project.id).count()} rules"
    )
    print(
        f"  - Strategy version completeness: {completeness.score_pct}% (missing: {completeness.missing})"
    )
    print(f"  - Backtest: {metrics['num_trades']} trades, net profit {metrics['net_profit']}")
    db.close()


if __name__ == "__main__":
    seed()
