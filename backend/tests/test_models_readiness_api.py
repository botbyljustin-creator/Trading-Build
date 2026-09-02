"""Thin integration check for GET /projects/{id}/models/readiness — the
scoring logic itself is covered by tests/test_readiness_service.py."""

from __future__ import annotations

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
    not _database_available(), reason="Requires a reachable Postgres database."
)


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_readiness_endpoint_reflects_manually_created_rules(client: TestClient):
    r = client.post("/api/v1/projects", json={"name": "Readiness API Test"})
    project_id = r.json()["id"]

    client.post(
        f"/api/v1/projects/{project_id}/rules",
        json={
            "category": "ENTRY",
            "natural_language_rule": "Enter on NASDAQ NQ FVG fill.",
            "quantifiability": "FULLY_QUANTIFIABLE",
        },
    )

    r = client.get(f"/api/v1/projects/{project_id}/models/readiness")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["series_id"] is None
    assert body[0]["total_rules"] == 1
    assert body[0]["nasdaq_relevant_rules"] == 1
    assert body[0]["score"] > 0


def test_readiness_endpoint_is_scoped_to_owning_project(client: TestClient):
    r1 = client.post("/api/v1/projects", json={"name": "Readiness Owner A"})
    project_a = r1.json()["id"]
    client.post(
        f"/api/v1/projects/{project_a}/rules",
        json={"category": "ENTRY", "natural_language_rule": "Rule in project A"},
    )

    r2 = client.post("/api/v1/projects", json={"name": "Readiness Owner B"})
    project_b = r2.json()["id"]

    body_b = client.get(f"/api/v1/projects/{project_b}/models/readiness").json()
    assert body_b == []
