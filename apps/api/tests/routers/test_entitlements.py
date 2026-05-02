"""Integration tests for GET /entitlements."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from core.dependencies import get_current_user, get_entitlements_service
from main import app

MOCK_USER = {"id": "user-123", "email": "test@example.com"}


def _raise_401() -> None:
    raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


@pytest.fixture
def mock_entitlements_service() -> MagicMock:
    service = MagicMock()
    service.get_entitlements.return_value = {
        "kit_pass": {
            "active": True,
            "season": "2026-27",
            "purchase_url": None,
        }
    }
    return service


@pytest.fixture(autouse=True)
def override_deps(mock_entitlements_service: MagicMock) -> None:
    app.dependency_overrides[get_entitlements_service] = lambda: mock_entitlements_service
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield
    app.dependency_overrides.clear()


def test_get_entitlements_returns_200_and_expected_shape(client: TestClient) -> None:
    resp = client.get("/entitlements")

    assert resp.status_code == 200
    assert resp.json() == {
        "kit_pass": {
            "active": True,
            "season": "2026-27",
            "purchase_url": None,
        }
    }


def test_get_entitlements_requires_auth(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = _raise_401
    resp = client.get("/entitlements")

    assert resp.status_code == 401


def test_get_entitlements_sets_cache_control_no_store(client: TestClient) -> None:
    resp = client.get("/entitlements")

    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"
