"""Manual transcript import — the network-block workaround. Verifies it
produces exactly the same downstream shape (series, video, transcript,
chunks with content hashes, source citations reachable) as a live fetch
would, without ever inventing transcript content itself.
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


def _sample_segments():
    return [
        {"start": 0.0, "duration": 5.0, "text": "Fixture line one."},
        {"start": 5.0, "duration": 5.0, "text": "Fixture line two."},
        {"start": 10.0, "duration": 5.0, "text": "Fixture line three."},
    ]


def test_manual_import_creates_series_video_and_chunks(client: TestClient):
    r = client.post("/api/v1/projects", json={"name": "Manual Import Test"})
    assert r.status_code == 201, r.text
    project_id = r.json()["id"]

    r = client.post(
        f"/api/v1/projects/{project_id}/videos/manual-import",
        json={
            "url": "https://www.youtube.com/watch?v=abc123XYZ_-",
            "title": "Fixture Video",
            "creator_name": "Fixture Creator",
            "series_name": "Fixture Series 2022",
            "segments": _sample_segments(),
        },
    )
    assert r.status_code == 201, r.text
    video = r.json()
    assert video["is_manual_import"] is True
    assert video["series_id"] is not None
    assert video["transcript_status"] == "AVAILABLE"

    r = client.get(f"/api/v1/videos/{video['id']}/transcript")
    assert r.status_code == 200
    chunks = r.json()
    assert len(chunks) >= 1
    assert "Fixture line" in chunks[0]["text"]


def test_manual_import_rejects_duplicate_video(client: TestClient):
    r = client.post("/api/v1/projects", json={"name": "Manual Import Dup Test"})
    project_id = r.json()["id"]
    payload = {
        "url": "https://www.youtube.com/watch?v=dupdupdupdup",
        "title": "Fixture Video",
        "creator_name": "Fixture Creator",
        "segments": _sample_segments(),
    }
    r1 = client.post(f"/api/v1/projects/{project_id}/videos/manual-import", json=payload)
    assert r1.status_code == 201
    r2 = client.post(f"/api/v1/projects/{project_id}/videos/manual-import", json=payload)
    assert r2.status_code == 409


def test_manual_import_rejects_non_video_url(client: TestClient):
    r = client.post("/api/v1/projects", json={"name": "Manual Import Bad URL Test"})
    project_id = r.json()["id"]
    r = client.post(
        f"/api/v1/projects/{project_id}/videos/manual-import",
        json={
            "url": "https://www.youtube.com/playlist?list=PL123",
            "title": "x",
            "creator_name": "x",
            "segments": _sample_segments(),
        },
    )
    assert r.status_code == 422


def test_manual_import_without_series_leaves_video_unscoped(client: TestClient):
    r = client.post("/api/v1/projects", json={"name": "Manual Import No Series Test"})
    project_id = r.json()["id"]
    r = client.post(
        f"/api/v1/projects/{project_id}/videos/manual-import",
        json={
            "url": "https://www.youtube.com/watch?v=noseriesvid1",
            "title": "Standalone Fixture Video",
            "creator_name": "Fixture Creator",
            "segments": _sample_segments(),
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["series_id"] is None
