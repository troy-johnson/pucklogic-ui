"""Integration tests for POST /exports/generate."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_rankings_repository
from main import app

SEASON = "2025-26"
WEIGHTS = {"nhl_com": 50.0}

DB_ROWS = [
    {
        "rank": 1,
        "season": SEASON,
        "players": {"id": "p1", "name": "McDavid", "team": "EDM", "position": "C"},
        "sources": {"name": "nhl_com", "display_name": "NHL.com"},
    },
]

EXCEL_BODY = {"season": SEASON, "weights": WEIGHTS, "export_type": "excel"}
PDF_BODY = {"season": SEASON, "weights": WEIGHTS, "export_type": "pdf"}


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_season.return_value = DB_ROWS
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_repo: MagicMock) -> None:
    app.dependency_overrides[get_rankings_repository] = lambda: mock_repo
    yield
    app.dependency_overrides.clear()


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
        body = {"season": SEASON, "weights": WEIGHTS, "export_type": "csv"}
        assert client.post("/exports/generate", json=body).status_code == 422

    def test_missing_season_returns_422(self, client: TestClient) -> None:
        body = {"weights": WEIGHTS, "export_type": "excel"}
        assert client.post("/exports/generate", json=body).status_code == 422
