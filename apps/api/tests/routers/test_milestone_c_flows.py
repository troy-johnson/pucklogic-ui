"""Direct Milestone C flow coverage across entitlements and gated exports."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.dependencies import (
    get_current_user,
    get_entitlements_service,
    get_league_profile_repository,
    get_projection_repository,
    get_scoring_config_repository,
    get_source_repository,
    get_subscription_repository,
)
from main import app
from services.entitlements import EntitlementsService


@pytest.fixture
def mock_sub_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_entitlements_state.return_value = {
        "draft_pass_balance": 0,
        "active": False,
        "season": None,
        "purchased_at": None,
    }
    repo.get_kit_pass_state.return_value = {
        "active": False,
        "season": None,
        "purchased_at": None,
    }
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_sub_repo: MagicMock) -> None:
    user = {"id": "user-123", "email": "test@example.com"}

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_subscription_repository] = lambda: mock_sub_repo
    app.dependency_overrides[get_entitlements_service] = lambda: EntitlementsService(
        subscription_repo=mock_sub_repo,
        frontend_url="https://app.example.com",
    )

    proj_repo = MagicMock()
    proj_repo.get_by_season.return_value = [
        {
            "player_id": "p1",
            "players": {"name": "Connor McDavid", "team": "EDM", "position": "C"},
            "sources": {"name": "hashtag", "user_id": None},
            "player_platform_positions": [{"positions": ["C"]}],
            "schedule_scores": [
                {"season": "2026-27", "schedule_score": 0.8, "off_night_games": 10}
            ],
            "g": 60,
            "a": 90,
            "plus_minus": None,
            "pim": None,
            "ppg": None,
            "ppa": None,
            "ppp": 50,
            "shg": None,
            "sha": None,
            "shp": None,
            "sog": 250,
            "fow": None,
            "fol": None,
            "hits": None,
            "blocks": None,
            "gp": 82,
            "gs": None,
            "w": None,
            "l": None,
            "ga": None,
            "sa": None,
            "sv": None,
            "sv_pct": None,
            "so": None,
            "otl": None,
        }
    ]
    sc_repo = MagicMock()
    sc_repo.get.return_value = {
        "id": "sc-1",
        "name": "Standard",
        "stat_weights": {"g": 3, "a": 2},
        "is_preset": True,
    }
    lp_repo = MagicMock()
    lp_repo.get.return_value = None
    src_repo = MagicMock()
    src_repo.get_by_names.return_value = {
        "hashtag": {"name": "hashtag", "user_id": None, "is_paid": False}
    }

    app.dependency_overrides[get_projection_repository] = lambda: proj_repo
    app.dependency_overrides[get_scoring_config_repository] = lambda: sc_repo
    app.dependency_overrides[get_league_profile_repository] = lambda: lp_repo
    app.dependency_overrides[get_source_repository] = lambda: src_repo

    yield
    app.dependency_overrides.clear()


def test_entitlements_lifecycle_and_export_gate(
    client: TestClient, mock_sub_repo: MagicMock
) -> None:
    body = {
        "season": "2026-27",
        "source_weights": {"hashtag": 1.0},
        "scoring_config_id": "sc-1",
        "platform": "espn",
        "export_type": "excel",
    }

    # Initial state: no pass => entitlements inactive + export blocked
    mock_sub_repo.get_entitlements_state.return_value = {
        "draft_pass_balance": 0,
        "active": False,
        "season": None,
        "purchased_at": None,
    }
    mock_sub_repo.get_kit_pass_state.return_value = {
        "active": False,
        "season": None,
        "purchased_at": None,
    }
    no_pass = client.get("/entitlements")
    assert no_pass.status_code == 200
    assert no_pass.json()["kit_pass"]["active"] is False
    blocked = client.post("/exports/generate", json=body)
    assert blocked.status_code == 403

    # Purchased/current-season active => entitlements active + export allowed
    mock_sub_repo.get_entitlements_state.return_value = {
        "draft_pass_balance": 0,
        "active": True,
        "season": "2026-27",
        "purchased_at": "2026-08-14T19:22:00Z",
    }
    mock_sub_repo.get_kit_pass_state.return_value = {
        "active": True,
        "season": "2026-27",
        "purchased_at": "2026-08-14T19:22:00Z",
    }
    active = client.get("/entitlements")
    assert active.status_code == 200
    assert active.json()["kit_pass"]["active"] is True
    with patch("routers.exports.generate_excel", return_value=b"XLSX"):
        allowed = client.post("/exports/generate", json=body)
    assert allowed.status_code == 200

    # Rollover/stale => entitlements inactive + export blocked again
    mock_sub_repo.get_entitlements_state.return_value = {
        "draft_pass_balance": 0,
        "active": False,
        "season": "2025-26",
        "purchased_at": "2025-08-14T19:22:00Z",
    }
    mock_sub_repo.get_kit_pass_state.return_value = {
        "active": False,
        "season": "2025-26",
        "purchased_at": "2025-08-14T19:22:00Z",
    }
    stale = client.get("/entitlements")
    assert stale.status_code == 200
    assert stale.json()["kit_pass"]["active"] is False
    blocked_again = client.post("/exports/generate", json=body)
    assert blocked_again.status_code == 403
