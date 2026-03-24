from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from models.schemas import TrendedPlayer, TrendsResponse
from routers.trends import _get_guarded_repo


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_response(has_trends: bool = True) -> TrendsResponse:
    if has_trends:
        return TrendsResponse(
            season="2025-26",
            has_trends=True,
            updated_at=datetime(2026, 8, 1, 8, 0, 0, tzinfo=UTC),
            players=[
                TrendedPlayer(
                    player_id="p-mcdavid",
                    name="Connor McDavid",
                    position="C",
                    team="EDM",
                    breakout_score=0.85,
                    regression_risk=0.10,
                    confidence=0.80,
                )
            ],
        )
    return TrendsResponse(season="2025-26", has_trends=False, updated_at=None, players=[])


class TestGetTrendsRouter:
    def test_503_when_models_none(self, client):
        app.state.models = None
        response = client.get("/trends?season=2025-26")
        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()

    def test_200_when_models_loaded(self, client):
        mock_repo = MagicMock()
        mock_repo.get_trends.return_value = _make_response(has_trends=True)
        app.dependency_overrides[_get_guarded_repo] = lambda: mock_repo

        response = client.get("/trends?season=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["has_trends"] is True
        assert len(data["players"]) == 1
        assert data["players"][0]["breakout_score"] == pytest.approx(0.85)

        app.dependency_overrides.clear()

    def test_has_trends_false_returns_200_not_503(self, client):
        """has_trends=False is a valid pre-training state — not an error."""
        mock_repo = MagicMock()
        mock_repo.get_trends.return_value = _make_response(has_trends=False)
        app.dependency_overrides[_get_guarded_repo] = lambda: mock_repo

        response = client.get("/trends?season=2025-26")
        assert response.status_code == 200
        assert response.json()["has_trends"] is False

        app.dependency_overrides.clear()

    def test_default_season_used_when_not_provided(self, client):
        mock_repo = MagicMock()
        mock_repo.get_trends.return_value = _make_response(has_trends=False)
        app.dependency_overrides[_get_guarded_repo] = lambda: mock_repo

        response = client.get("/trends")  # no ?season= param
        assert response.status_code == 200

        app.dependency_overrides.clear()
