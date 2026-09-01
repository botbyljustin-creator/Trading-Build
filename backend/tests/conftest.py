"""Shared pytest fixtures.

Tests never require a live Postgres/Redis: the FastAPI app under test uses
dependency overrides for the health-check dependencies so component status
can be simulated deterministically.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
        app.dependency_overrides.clear()
