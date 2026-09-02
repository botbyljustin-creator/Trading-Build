"""End-to-end integration test across the whole pipeline: project -> rules
-> compile -> codegen -> backtest -> robustness -> report.

Requires a real Postgres database (the one `DATABASE_URL` points at) since
it exercises actual ORM writes/reads through the API, and a CSV data
directory for the backtest step. Skipped with a clear reason rather than
failing if either prerequisite isn't available — the rest of the suite
(unit tests for the compiler, codegen, backtest engine, etc.) needs neither
and always runs.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import get_engine


def _database_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _database_available(), reason="Integration test requires a reachable Postgres database."
)


@pytest.fixture
def csv_market_data(tmp_path, monkeypatch) -> str:
    rng = np.random.default_rng(42)
    n = 1500
    index = pd.date_range("2024-01-02 09:30", periods=n, freq="5min", tz="UTC")
    close = 18000 + np.cumsum(rng.normal(0, 3, size=n))
    df = pd.DataFrame(
        {
            "timestamp": index,
            "open": close + rng.normal(0, 1, size=n),
            "high": close + rng.uniform(1, 5, size=n),
            "low": close - rng.uniform(1, 5, size=n),
            "close": close,
            "volume": rng.integers(100, 5000, size=n),
        }
    )
    df.to_csv(tmp_path / "TESTSYM.csv", index=False)
    (tmp_path / "TESTSYM.meta.json").write_text(
        json.dumps(
            {"timezone": "America/New_York", "asset_type": "CFD", "exchange_session": "CME_GLOBEX"}
        )
    )
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MARKET_DATA_CSV_DIR", str(tmp_path))
    yield str(tmp_path)
    get_settings.cache_clear()


@pytest.fixture
def integration_client(csv_market_data) -> TestClient:
    from app.workers.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


RULES_PAYLOAD = [
    {"category": "MARKET", "natural_language_rule": "Synthetic test instrument"},
    {"category": "TIMEFRAME", "natural_language_rule": "5 minute"},
    {
        "category": "SESSION",
        "natural_language_rule": "9:30-11:30 New York",
        "machine_readable_rule": {
            "start_time": "09:30",
            "end_time": "11:30",
            "timezone": "America/New_York",
        },
    },
    {
        "category": "BIAS",
        "natural_language_rule": "Price above 10 EMA",
        "machine_readable_rule": {
            "type": "price_above_ma",
            "length": 10,
            "ma_type": "EMA",
            "direction": "long",
        },
    },
    {
        "category": "SETUP",
        "natural_language_rule": "Always eligible (test)",
        "machine_readable_rule": {"type": "always_true"},
    },
    {
        "category": "CONFIRMATION",
        "natural_language_rule": "Always eligible (test)",
        "machine_readable_rule": {"type": "always_true"},
    },
    {
        "category": "ENTRY",
        "natural_language_rule": "Always eligible (test)",
        "machine_readable_rule": {"type": "always_true"},
    },
    {
        "category": "STOP_LOSS",
        "natural_language_rule": "5 point stop",
        "machine_readable_rule": {"method": "FIXED_POINTS", "value": 5.0},
    },
    {
        "category": "TAKE_PROFIT",
        "natural_language_rule": "2R target",
        "machine_readable_rule": {"method": "R_MULTIPLE", "value": 2.0},
    },
    {
        "category": "POSITION_SIZING",
        "natural_language_rule": "1% risk per trade",
        "machine_readable_rule": {"method": "RISK_PERCENT", "value": 1.0, "max_trades_per_day": 3},
    },
    {"category": "INVALIDATION", "natural_language_rule": "Invalid if price closes back below EMA"},
    {
        "category": "TRADE_MANAGEMENT",
        "natural_language_rule": "One position at a time, no overnight",
        "machine_readable_rule": {
            "allow_multiple_concurrent_positions": False,
            "allow_overnight_positions": False,
        },
    },
]


def test_full_pipeline_project_to_backtest_report(integration_client: TestClient):
    client = integration_client

    r = client.post("/api/v1/projects", json={"name": "Integration Test Project"})
    assert r.status_code == 201, r.text
    project = r.json()

    rule_ids = []
    for payload in RULES_PAYLOAD:
        r = client.post(f"/api/v1/projects/{project['id']}/rules", json=payload)
        assert r.status_code == 201, r.text
        rule_ids.append(r.json()["id"])

    r = client.post(
        f"/api/v1/projects/{project['id']}/strategies", json={"name": "Integration Test Strategy"}
    )
    assert r.status_code == 201, r.text
    strategy = r.json()

    r = client.post(
        f"/api/v1/strategies/{strategy['id']}/versions/compile", json={"rule_ids": rule_ids}
    )
    assert r.status_code == 201, r.text
    version = r.json()
    assert version["completeness_score"] == 100.0
    assert version["missing_fields"] == []

    r = client.post(f"/api/v1/strategy-versions/{version['id']}/generate-code")
    assert r.status_code == 200, r.text
    code_rows = {row["language"]: row["code"] for row in r.json()}
    assert set(code_rows) == {"PINE", "PYTHON"}
    assert "STRATEGYFORGE_SPEC_JSON_BEGIN" in code_rows["PINE"]
    assert "STRATEGYFORGE_SPEC_JSON_BEGIN" in code_rows["PYTHON"]

    r = client.post(
        f"/api/v1/strategy-versions/{version['id']}/backtests",
        json={
            "provider": "csv",
            "symbol": "TESTSYM",
            "timezone": "America/New_York",
            "asset_type": "CFD",
            "date_start": "2024-01-02T00:00:00Z",
            "date_end": "2024-01-10T00:00:00Z",
            "starting_balance": 10000,
            "risk_pct_per_trade": 1.0,
            "commission_per_trade": 1.0,
            "slippage_pct": 0.01,
        },
    )
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["status"] == "SUCCESS", job

    backtest_id = job["result_ref"]["backtest_id"]
    r = client.get(f"/api/v1/backtests/{backtest_id}")
    assert r.status_code == 200
    backtest = r.json()
    assert backtest["status"] == "COMPLETE"
    assert backtest["metrics"]["num_trades"] >= 0

    r = client.post(f"/api/v1/backtests/{backtest_id}/robustness")
    assert r.status_code == 202
    assert r.json()["status"] == "SUCCESS"

    r = client.post(
        f"/api/v1/strategy-versions/{version['id']}/reports", json={"backtest_id": backtest_id}
    )
    assert r.status_code == 202
    report_job = r.json()
    assert report_job["status"] == "SUCCESS", report_job
    report_id = report_job["result_ref"]["report_id"]

    r = client.get(f"/api/v1/reports/{report_id}")
    assert r.status_code == 200
    report = r.json()["content_json"]
    assert report["strategy_summary"]["completeness_score_pct"] == 100.0
    assert "backtest_results" in report


def test_ai_assumption_rule_cannot_be_compiled(integration_client: TestClient):
    """Enforces the core safety property end-to-end through the real API +
    database, not just at the unit level: an AI_ASSUMPTION rule must never
    be silently compiled into a strategy."""
    client = integration_client

    r = client.post("/api/v1/projects", json={"name": "AI Assumption Guard Test"})
    project = r.json()

    r = client.post(
        f"/api/v1/projects/{project['id']}/strategies", json={"name": "Guard Test Strategy"}
    )
    strategy = r.json()

    # Insert an AI_ASSUMPTION rule directly since there's no API path that
    # creates one at anything other than EXTRACTED/AI_ASSUMPTION status —
    # exactly the point: only extraction can create it, and extraction
    # output can never be compiled without a review step in between.
    from app.core.db import get_session_factory
    from app.models.enums import RuleCategory, RuleStatus
    from app.models.rule import Rule

    db = get_session_factory()()
    try:
        rule = Rule(
            project_id=project["id"],
            category=RuleCategory.ENTRY,
            natural_language_rule="Inferred entry rule, never confirmed by a human",
            confidence=0.4,
            status=RuleStatus.AI_ASSUMPTION,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        rule_id = str(rule.id)
    finally:
        db.close()

    r = client.post(
        f"/api/v1/strategies/{strategy['id']}/versions/compile", json={"rule_ids": [rule_id]}
    )
    assert r.status_code == 422, r.text
    assert "AI_ASSUMPTION" in r.text
