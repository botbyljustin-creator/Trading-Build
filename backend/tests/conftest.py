"""Shared pytest fixtures.

Tests never require a live Postgres/Redis: the FastAPI app under test uses
dependency overrides for the health-check dependencies so component status
can be simulated deterministically.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Imported lazily so pure-unit-test modules (e.g. strategy compiler,
    # codegen, backtest engine tests) can run without every API route
    # module existing/importing cleanly yet.
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
        app.dependency_overrides.clear()
