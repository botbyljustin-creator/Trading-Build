"""Quantification workflow: proposals are never applied automatically and
never confused with the rule's own natural_language_rule / quantifiability.
"""

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


def _make_discretionary_rule(client: TestClient) -> tuple[str, str]:
    r = client.post("/api/v1/projects", json={"name": "Quantification Workflow Test"})
    assert r.status_code == 201, r.text
    project_id = r.json()["id"]

    r = client.post(
        f"/api/v1/projects/{project_id}/rules",
        json={
            "category": "SETUP",
            "natural_language_rule": "Wait for a clean shift in market structure, use your judgment.",
        },
    )
    assert r.status_code == 201, r.text
    return project_id, r.json()["id"]


def test_propose_quantifications_never_touches_the_original_rule_text(client: TestClient):
    project_id, rule_id = _make_discretionary_rule(client)

    r = client.post(
        f"/api/v1/rules/{rule_id}/quantifications",
        json={
            "proposals": [
                {
                    "label": "A",
                    "description": "Candle body > 1.5x the 20-period ATR",
                    "machine_readable_rule": {
                        "type": "atr_multiple",
                        "multiple": 1.5,
                        "lookback": 20,
                    },
                },
                {
                    "label": "B",
                    "description": "Break of the most recent swing high/low by at least 2 ticks",
                    "machine_readable_rule": {"type": "swing_break", "min_ticks": 2},
                },
            ]
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rule_id"] == rule_id
    assert len(body["proposals"]) == 2
    assert body["selected_index"] is None
    assert body["user_defined_alternative"] is None

    rule = client.get(f"/api/v1/projects/{project_id}/rules").json()[0]
    assert (
        rule["natural_language_rule"]
        == "Wait for a clean shift in market structure, use your judgment."
    )
    assert rule["quantifiability"] is None


def test_selecting_a_proposal_by_index(client: TestClient):
    _, rule_id = _make_discretionary_rule(client)
    propose = client.post(
        f"/api/v1/rules/{rule_id}/quantifications",
        json={"proposals": [{"label": "A", "description": "d", "machine_readable_rule": {"x": 1}}]},
    ).json()

    r = client.post(
        f"/api/v1/rule-quantifications/{propose['id']}/select", json={"selected_index": 0}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["selected_index"] == 0
    assert body["user_defined_alternative"] is None
    assert body["selected_at"] is not None


def test_selecting_out_of_range_index_is_rejected(client: TestClient):
    _, rule_id = _make_discretionary_rule(client)
    propose = client.post(
        f"/api/v1/rules/{rule_id}/quantifications",
        json={"proposals": [{"label": "A", "description": "d", "machine_readable_rule": {"x": 1}}]},
    ).json()

    r = client.post(
        f"/api/v1/rule-quantifications/{propose['id']}/select", json={"selected_index": 5}
    )
    assert r.status_code == 422


def test_user_can_define_their_own_alternative_instead_of_a_proposal(client: TestClient):
    _, rule_id = _make_discretionary_rule(client)
    propose = client.post(
        f"/api/v1/rules/{rule_id}/quantifications",
        json={"proposals": [{"label": "A", "description": "d", "machine_readable_rule": {"x": 1}}]},
    ).json()

    r = client.post(
        f"/api/v1/rule-quantifications/{propose['id']}/select",
        json={"user_defined_alternative": {"type": "custom", "note": "my own definition"}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["selected_index"] is None
    assert body["user_defined_alternative"] == {"type": "custom", "note": "my own definition"}


def test_selection_requires_exactly_one_choice(client: TestClient):
    _, rule_id = _make_discretionary_rule(client)
    propose = client.post(
        f"/api/v1/rules/{rule_id}/quantifications",
        json={"proposals": [{"label": "A", "description": "d", "machine_readable_rule": {"x": 1}}]},
    ).json()

    r = client.post(f"/api/v1/rule-quantifications/{propose['id']}/select", json={})
    assert r.status_code == 422

    r = client.post(
        f"/api/v1/rule-quantifications/{propose['id']}/select",
        json={"selected_index": 0, "user_defined_alternative": {"type": "custom"}},
    )
    assert r.status_code == 422


def test_reproposing_resets_any_prior_selection(client: TestClient):
    _, rule_id = _make_discretionary_rule(client)
    propose = client.post(
        f"/api/v1/rules/{rule_id}/quantifications",
        json={"proposals": [{"label": "A", "description": "d", "machine_readable_rule": {"x": 1}}]},
    ).json()
    client.post(f"/api/v1/rule-quantifications/{propose['id']}/select", json={"selected_index": 0})

    reproposed = client.post(
        f"/api/v1/rules/{rule_id}/quantifications",
        json={
            "proposals": [
                {"label": "A", "description": "revised", "machine_readable_rule": {"x": 2}}
            ]
        },
    ).json()
    assert reproposed["selected_index"] is None
    assert reproposed["proposals"][0]["description"] == "revised"


def test_quantifications_are_scoped_to_the_owning_project(client: TestClient):
    _, rule_id = _make_discretionary_rule(client)
    r = client.get(f"/api/v1/rules/{rule_id}/quantifications")
    assert r.status_code == 200
    assert r.json() is None
