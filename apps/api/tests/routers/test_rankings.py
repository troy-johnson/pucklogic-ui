"""Integration tests for POST /rankings/compute."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_league_profile_repository,
    get_projection_repository,
    get_scoring_config_repository,
    get_source_repository,
    get_subscription_repository,
)
from main import app

MOCK_USER = {"id": "user-123", "email": "test@example.com"}

SEASON = "2025-26"
SOURCE_WEIGHTS = {"hashtag": 1.0, "dailyfaceoff": 0.5}
SCORING_CONFIG_ID = "sc-1"
PLATFORM = "espn"

VALID_BODY = {
    "season": SEASON,
    "source_weights": SOURCE_WEIGHTS,
    "scoring_config_id": SCORING_CONFIG_ID,
    "platform": PLATFORM,
}

PROJECTION_ROWS = [
    {
        "player_id": "p1",
        "players": {"name": "Connor McDavid", "team": "EDM", "position": "C"},
        "sources": {"name": "hashtag", "user_id": None},
        "player_platform_positions": [{"positions": ["C", "F"]}],
        "schedule_scores": [{"season": "2025-26", "schedule_score": 0.75, "off_night_games": 12}],
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

SCORING_CONFIG_ROW = {
    "id": SCORING_CONFIG_ID,
    "name": "Standard",
    "stat_weights": {"g": 3, "a": 2, "ppp": 1},
    "is_preset": True,
}

CACHED_RANKINGS = [
    {
        "composite_rank": 1,
        "player_id": "p1",
        "name": "Connor McDavid",
        "team": "EDM",
        "default_position": "C",
        "platform_positions": ["C", "F"],
        "projected_fantasy_points": 290.0,
        "vorp": None,
        "schedule_score": 0.75,
        "off_night_games": 12,
        "source_count": 1,
        "projected_stats": {
            "g": 60, "a": 90, "plus_minus": None, "pim": None,
            "ppg": None, "ppa": None, "ppp": 50, "shg": None, "sha": None,
            "shp": None, "sog": 250, "fow": None, "fol": None,
            "hits": None, "blocks": None, "gp": 82,
            "gs": None, "w": None, "l": None, "ga": None,
            "sa": None, "sv": None, "sv_pct": None, "so": None, "otl": None,
        },
        "breakout_score": None,
        "regression_risk": None,
    }
]


@pytest.fixture
def mock_proj_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_season.return_value = PROJECTION_ROWS
    return repo


@pytest.fixture
def mock_sc_repo() -> MagicMock:
    repo = MagicMock()
    repo.get.return_value = SCORING_CONFIG_ROW
    return repo


@pytest.fixture
def mock_lp_repo() -> MagicMock:
    repo = MagicMock()
    repo.get.return_value = None
    return repo


@pytest.fixture
def mock_src_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_names.return_value = {
        "hashtag": {"name": "hashtag", "user_id": None, "is_paid": False},
        "dailyfaceoff": {"name": "dailyfaceoff", "user_id": None, "is_paid": False},
    }
    return repo


@pytest.fixture
def mock_sub_repo() -> MagicMock:
    repo = MagicMock()
    repo.is_active.return_value = True
    return repo


@pytest.fixture
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.get_rankings.return_value = None
    return cache


@pytest.fixture(autouse=True)
def override_deps(
    mock_proj_repo: MagicMock,
    mock_sc_repo: MagicMock,
    mock_lp_repo: MagicMock,
    mock_src_repo: MagicMock,
    mock_sub_repo: MagicMock,
    mock_cache: MagicMock,
) -> None:
    app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
    app.dependency_overrides[get_scoring_config_repository] = lambda: mock_sc_repo
    app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
    app.dependency_overrides[get_source_repository] = lambda: mock_src_repo
    app.dependency_overrides[get_subscription_repository] = lambda: mock_sub_repo
    app.dependency_overrides[get_cache_service] = lambda: mock_cache
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestComputeRankings:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.post("/rankings/compute", json=VALID_BODY).status_code == 200

    def test_response_has_required_fields(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert "season" in data
        assert "computed_at" in data
        assert "cached" in data
        assert "rankings" in data

    def test_season_echoed_in_response(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert data["season"] == SEASON

    def test_cached_false_on_cache_miss(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert data["cached"] is False

    def test_rankings_list_returned(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert isinstance(data["rankings"], list)

    def test_ranked_player_has_projected_fantasy_points(
        self, client: TestClient
    ) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert len(data["rankings"]) > 0
        player = data["rankings"][0]
        assert "projected_fantasy_points" in player

    def test_ranked_player_has_projected_stats(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        player = data["rankings"][0]
        assert "projected_stats" in player

    def test_vorp_null_without_league_profile(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        player = data["rankings"][0]
        assert player["vorp"] is None

    def test_cache_is_populated_on_miss(
        self, client: TestClient, mock_cache: MagicMock
    ) -> None:
        client.post("/rankings/compute", json=VALID_BODY)
        mock_cache.set_rankings.assert_called_once()

    def test_cache_hit_returns_cached_true(
        self, client: TestClient, mock_cache: MagicMock
    ) -> None:
        mock_cache.get_rankings.return_value = CACHED_RANKINGS
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert data["cached"] is True

    def test_proj_repo_not_called_on_cache_hit(
        self, client: TestClient, mock_cache: MagicMock, mock_proj_repo: MagicMock
    ) -> None:
        mock_cache.get_rankings.return_value = CACHED_RANKINGS
        client.post("/rankings/compute", json=VALID_BODY)
        mock_proj_repo.get_by_season.assert_not_called()

    def test_missing_season_returns_422(self, client: TestClient) -> None:
        body = {k: v for k, v in VALID_BODY.items() if k != "season"}
        assert client.post("/rankings/compute", json=body).status_code == 422

    def test_missing_source_weights_returns_422(self, client: TestClient) -> None:
        body = {k: v for k, v in VALID_BODY.items() if k != "source_weights"}
        assert client.post("/rankings/compute", json=body).status_code == 422

    def test_all_zero_weights_returns_422(self, client: TestClient) -> None:
        body = {**VALID_BODY, "source_weights": {"hashtag": 0.0}}
        assert client.post("/rankings/compute", json=body).status_code == 422

    def test_auth_checked_even_on_cache_hit(
        self, client: TestClient, mock_cache: MagicMock, mock_src_repo: MagicMock
    ) -> None:
        """A warm cache must not bypass access control — unknown source → 400 even if cached."""
        mock_cache.get_rankings.return_value = CACHED_RANKINGS
        mock_src_repo.get_by_names.return_value = {}  # none of the requested sources exist
        resp = client.post("/rankings/compute", json=VALID_BODY)
        assert resp.status_code == 400

    def test_scoring_config_not_found_returns_404(
        self, client: TestClient, mock_sc_repo: MagicMock
    ) -> None:
        mock_sc_repo.get.return_value = None
        assert client.post("/rankings/compute", json=VALID_BODY).status_code == 404


class TestSourceWeightsValidation:
    def test_unknown_source_key_returns_400(
        self, client: TestClient, mock_src_repo: MagicMock
    ) -> None:
        mock_src_repo.get_by_names.return_value = {}  # none found
        resp = client.post("/rankings/compute", json=VALID_BODY)
        assert resp.status_code == 400
        assert "Unknown source key" in resp.json()["detail"]

    def test_inaccessible_user_source_returns_400(
        self, client: TestClient, mock_src_repo: MagicMock
    ) -> None:
        mock_src_repo.get_by_names.return_value = {
            "hashtag": {"name": "hashtag", "user_id": "other-user", "is_paid": False},
            "dailyfaceoff": {"name": "dailyfaceoff", "user_id": None, "is_paid": False},
        }
        resp = client.post("/rankings/compute", json=VALID_BODY)
        assert resp.status_code == 400

    def test_paid_source_without_subscription_returns_403(
        self, client: TestClient, mock_src_repo: MagicMock, mock_sub_repo: MagicMock
    ) -> None:
        mock_src_repo.get_by_names.return_value = {
            "hashtag": {"name": "hashtag", "user_id": None, "is_paid": True},
        }
        mock_sub_repo.is_active.return_value = False
        body = {**VALID_BODY, "source_weights": {"hashtag": 1.0}}
        resp = client.post("/rankings/compute", json=body)
        assert resp.status_code == 403
        assert "subscription" in resp.json()["detail"]

    def test_paid_source_with_subscription_succeeds(
        self, client: TestClient, mock_src_repo: MagicMock, mock_sub_repo: MagicMock
    ) -> None:
        mock_src_repo.get_by_names.return_value = {
            "hashtag": {"name": "hashtag", "user_id": None, "is_paid": True},
        }
        mock_sub_repo.is_active.return_value = True
        body = {**VALID_BODY, "source_weights": {"hashtag": 1.0}}
        resp = client.post("/rankings/compute", json=body)
        assert resp.status_code == 200
