"""Integration tests for POST /exports/generate."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from core.dependencies import (
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

EXCEL_BODY = {
    "season": SEASON,
    "source_weights": {"hashtag": 1.0},
    "scoring_config_id": "sc-1",
    "platform": "espn",
    "export_type": "excel",
}
PDF_BODY = {**EXCEL_BODY, "export_type": "pdf"}

SCORING_CONFIG_ROW = {
    "id": "sc-1",
    "name": "Standard",
    "stat_weights": {"g": 3, "a": 2},
    "is_preset": True,
}

PROJECTION_ROWS = [
    {
        "player_id": "p1",
        "players": {"name": "Connor McDavid", "team": "EDM", "position": "C"},
        "sources": {"name": "hashtag", "user_id": None},
        "player_platform_positions": [{"positions": ["C"]}],
        "schedule_scores": [{"season": "2025-26", "schedule_score": 0.8, "off_night_games": 10}],
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
    }
    return repo


@pytest.fixture
def mock_sub_repo() -> MagicMock:
    repo = MagicMock()
    repo.is_active.return_value = True
    return repo


@pytest.fixture(autouse=True)
def override_deps(
    mock_proj_repo: MagicMock,
    mock_sc_repo: MagicMock,
    mock_lp_repo: MagicMock,
    mock_src_repo: MagicMock,
    mock_sub_repo: MagicMock,
) -> None:
    app.dependency_overrides[get_projection_repository] = lambda: mock_proj_repo
    app.dependency_overrides[get_scoring_config_repository] = lambda: mock_sc_repo
    app.dependency_overrides[get_league_profile_repository] = lambda: mock_lp_repo
    app.dependency_overrides[get_source_repository] = lambda: mock_src_repo
    app.dependency_overrides[get_subscription_repository] = lambda: mock_sub_repo
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield
    app.dependency_overrides.clear()


def _raise_401() -> None:
    raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


class TestGenerateExcelExport:
    def test_returns_200(self, client: TestClient) -> None:
        with patch("routers.exports.generate_excel", return_value=b"XLSX"):
            assert client.post("/exports/generate", json=EXCEL_BODY).status_code == 200

    def test_content_type_is_xlsx(self, client: TestClient) -> None:
        with patch("routers.exports.generate_excel", return_value=b"XLSX"):
            resp = client.post("/exports/generate", json=EXCEL_BODY)
        assert "spreadsheetml" in resp.headers["content-type"]

    def test_content_disposition_is_attachment(self, client: TestClient) -> None:
        with patch("routers.exports.generate_excel", return_value=b"XLSX"):
            resp = client.post("/exports/generate", json=EXCEL_BODY)
        assert "attachment" in resp.headers["content-disposition"]
        assert ".xlsx" in resp.headers["content-disposition"]

    def test_returns_excel_bytes(self, client: TestClient) -> None:
        with patch("routers.exports.generate_excel", return_value=b"XLSXDATA"):
            resp = client.post("/exports/generate", json=EXCEL_BODY)
        assert resp.content == b"XLSXDATA"


class TestGeneratePdfExport:
    def test_returns_200(self, client: TestClient) -> None:
        with patch("routers.exports.generate_pdf", return_value=b"%PDF"):
            assert client.post("/exports/generate", json=PDF_BODY).status_code == 200

    def test_content_type_is_pdf(self, client: TestClient) -> None:
        with patch("routers.exports.generate_pdf", return_value=b"%PDF"):
            resp = client.post("/exports/generate", json=PDF_BODY)
        assert resp.headers["content-type"] == "application/pdf"

    def test_content_disposition_is_pdf_attachment(self, client: TestClient) -> None:
        with patch("routers.exports.generate_pdf", return_value=b"%PDF"):
            resp = client.post("/exports/generate", json=PDF_BODY)
        assert "attachment" in resp.headers["content-disposition"]
        assert ".pdf" in resp.headers["content-disposition"]


class TestExportValidation:
    def test_invalid_export_type_returns_422(self, client: TestClient) -> None:
        body = {**EXCEL_BODY, "export_type": "csv"}
        assert client.post("/exports/generate", json=body).status_code == 422

    def test_bundle_export_type_returns_422(self, client: TestClient) -> None:
        body = {**EXCEL_BODY, "export_type": "bundle"}
        assert client.post("/exports/generate", json=body).status_code == 422

    def test_missing_season_returns_422(self, client: TestClient) -> None:
        body = {k: v for k, v in EXCEL_BODY.items() if k != "season"}
        assert client.post("/exports/generate", json=body).status_code == 422

    def test_all_zero_weights_returns_422(self, client: TestClient) -> None:
        body = {**EXCEL_BODY, "source_weights": {"hashtag": 0.0}}
        assert client.post("/exports/generate", json=body).status_code == 422


class TestAuthRequired:
    @pytest.fixture(autouse=True)
    def reject_auth(self) -> None:
        app.dependency_overrides[get_current_user] = _raise_401
        yield

    def test_unauthenticated_request_returns_401(self, client: TestClient) -> None:
        resp = client.post("/exports/generate", json=EXCEL_BODY)
        assert resp.status_code == 401


class TestKitPassGating:
    def test_generate_export_returns_403_when_user_lacks_active_kit_pass(
        self,
        client: TestClient,
        mock_sub_repo: MagicMock,
    ) -> None:
        mock_sub_repo.is_active.return_value = False

        resp = client.post("/exports/generate", json=EXCEL_BODY)

        assert resp.status_code == 403
        assert resp.json()["detail"] == "active draft pass required"
