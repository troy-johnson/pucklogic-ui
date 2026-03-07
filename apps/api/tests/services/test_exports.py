"""Unit tests for services/exports.py — generate_excel and generate_pdf.

generate_excel: tested for real (openpyxl is pure Python, no system deps).
generate_pdf:   WeasyPrint requires system libs (Cairo/Pango), so the entire
                weasyprint module is injected into sys.modules as a MagicMock;
                all HTML-construction logic is validated against the HTML string
                passed to the mock.
"""

from __future__ import annotations

import io
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from openpyxl import load_workbook

from services.exports import generate_excel, generate_pdf

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

SEASON = "2025-26"

PLAYER_A: dict[str, Any] = {
    "composite_rank": 1,
    "name": "Connor McDavid",
    "team": "EDM",
    "position": "C",
    "composite_score": 0.9823,
    "source_ranks": {"dobber": 1, "nhl_com": 2},
}

PLAYER_B: dict[str, Any] = {
    "composite_rank": 2,
    "name": "Nathan MacKinnon",
    "team": "COL",
    "position": "C",
    "composite_score": 0.9541,
    "source_ranks": {"dobber": 2, "nhl_com": 1},
}

RANKINGS = [PLAYER_A, PLAYER_B]


def _make_weasyprint_mock(write_pdf_return: bytes = b"%PDF-1.4") -> MagicMock:
    """Return a fake weasyprint module whose HTML class behaves correctly."""
    mock_html_cls = MagicMock()
    mock_html_cls.return_value.write_pdf.return_value = write_pdf_return
    mock_module = MagicMock()
    mock_module.HTML = mock_html_cls
    return mock_module


def _capture_html(rankings: list[dict[str, Any]], season: str) -> str:
    """Run generate_pdf with a mocked weasyprint and return the HTML string."""
    captured: dict[str, str] = {}

    def fake_html(*args: object, **kwargs: object) -> MagicMock:
        captured["html"] = str(kwargs.get("string", args[0] if args else ""))
        mock = MagicMock()
        mock.write_pdf.return_value = b"%PDF-1.4"
        return mock

    mock_module = MagicMock()
    mock_module.HTML.side_effect = fake_html

    with patch.dict(sys.modules, {"weasyprint": mock_module}):
        generate_pdf(rankings, season)

    return captured["html"]


# ---------------------------------------------------------------------------
# generate_excel — real openpyxl tests (no mocking needed)
# ---------------------------------------------------------------------------


class TestGenerateExcel:
    def test_returns_bytes(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        assert isinstance(result, bytes)

    def test_bytes_are_valid_xlsx(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        wb = load_workbook(io.BytesIO(result))
        assert wb is not None

    def test_worksheet_title_contains_season(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        wb = load_workbook(io.BytesIO(result))
        assert SEASON in wb.active.title

    def test_header_row_base_columns(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        headers = [ws.cell(1, col).value for col in range(1, 6)]
        assert headers == ["Rank", "Player", "Team", "Position", "Score"]

    def test_source_columns_appended_to_header(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        # source_names are sorted: dobber → "Dobber", nhl_com → "Nhl Com"
        assert ws.cell(1, 6).value == "Dobber"
        assert ws.cell(1, 7).value == "Nhl Com"

    def test_data_rows_count(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        # 1 header + 2 data rows = 3 rows total
        assert ws.max_row == 3

    def test_first_data_row_values(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        assert ws.cell(2, 1).value == 1
        assert ws.cell(2, 2).value == "Connor McDavid"
        assert ws.cell(2, 3).value == "EDM"
        assert ws.cell(2, 4).value == "C"
        assert ws.cell(2, 5).value == pytest.approx(0.9823, abs=1e-6)

    def test_source_rank_values_in_data_row(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        # sources sorted: dobber(col6)=1, nhl_com(col7)=2 for McDavid
        assert ws.cell(2, 6).value == 1
        assert ws.cell(2, 7).value == 2

    def test_second_data_row_values(self) -> None:
        result = generate_excel(RANKINGS, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        assert ws.cell(3, 1).value == 2
        assert ws.cell(3, 2).value == "Nathan MacKinnon"
        assert ws.cell(3, 3).value == "COL"

    def test_missing_optional_fields_use_falsy_value(self) -> None:
        """team/position absent → cell value is None or '' (openpyxl normalises)."""
        rankings = [
            {
                "composite_rank": 1,
                "name": "Unknown Player",
                "composite_score": 0.5,
                "source_ranks": {},
            }
        ]
        result = generate_excel(rankings, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        assert ws.cell(2, 3).value in (None, "")   # team
        assert ws.cell(2, 4).value in (None, "")   # position

    def test_empty_rankings_produces_header_only(self) -> None:
        result = generate_excel([], SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        assert ws.max_row == 1
        assert ws.cell(1, 1).value == "Rank"

    def test_missing_source_rank_falls_back_to_falsy(self) -> None:
        """A player missing one source's rank should write '' or None, not raise."""
        rankings = [
            {
                "composite_rank": 1,
                "name": "McDavid",
                "team": "EDM",
                "position": "C",
                "composite_score": 0.99,
                "source_ranks": {"dobber": 1, "nhl_com": 2},
            },
            {
                "composite_rank": 2,
                "name": "Draisaitl",
                "team": "EDM",
                "position": "C",
                "composite_score": 0.95,
                "source_ranks": {"dobber": 3},  # nhl_com missing
            },
        ]
        result = generate_excel(rankings, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        # row 3, col 7 (nhl_com) for Draisaitl
        assert ws.cell(3, 7).value in (None, "")

    def test_single_player_no_sources(self) -> None:
        rankings = [
            {
                "composite_rank": 1,
                "name": "Auston Matthews",
                "team": "TOR",
                "position": "C",
                "composite_score": 0.88,
                "source_ranks": {},
            }
        ]
        result = generate_excel(rankings, SEASON)
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        # Only base 5 headers, no extra source columns
        assert ws.max_column == 5


# ---------------------------------------------------------------------------
# generate_pdf — mocked WeasyPrint via sys.modules; validates HTML construction
# ---------------------------------------------------------------------------


class TestGeneratePdf:
    def test_returns_bytes(self) -> None:
        mock_module = _make_weasyprint_mock()
        with patch.dict(sys.modules, {"weasyprint": mock_module}):
            result = generate_pdf(RANKINGS, SEASON)
        assert isinstance(result, bytes)

    def test_returns_pdf_bytes_from_write_pdf(self) -> None:
        mock_module = _make_weasyprint_mock(b"%PDF-1.4 custom")
        with patch.dict(sys.modules, {"weasyprint": mock_module}):
            result = generate_pdf(RANKINGS, SEASON)
        assert result == b"%PDF-1.4 custom"

    def test_html_contains_season(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        assert SEASON in html

    def test_html_contains_player_names(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        assert "Connor McDavid" in html
        assert "Nathan MacKinnon" in html

    def test_html_contains_teams(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        assert "EDM" in html
        assert "COL" in html

    def test_html_contains_positions(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        assert ">C<" in html

    def test_html_contains_composite_ranks(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        assert ">1<" in html
        assert ">2<" in html

    def test_html_contains_source_headers(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        # sorted: dobber → "Dobber", nhl_com → "Nhl Com"
        assert "Dobber" in html
        assert "Nhl Com" in html

    def test_html_contains_source_rank_values(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        assert ">1<" in html
        assert ">2<" in html

    def test_html_missing_source_rank_shows_em_dash(self) -> None:
        rankings = [
            {
                "composite_rank": 1,
                "name": "McDavid",
                "team": "EDM",
                "position": "C",
                "composite_score": 0.99,
                "source_ranks": {"dobber": 1},  # nhl_com absent
            },
            {
                "composite_rank": 2,
                "name": "Draisaitl",
                "team": "EDM",
                "position": "C",
                "composite_score": 0.95,
                "source_ranks": {"nhl_com": 2},  # dobber absent
            },
        ]
        html = _capture_html(rankings, SEASON)
        assert "—" in html

    def test_html_score_formatted_to_4_decimal_places(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        assert "0.9823" in html
        assert "0.9541" in html

    def test_empty_rankings_produces_valid_html_structure(self) -> None:
        html = _capture_html([], SEASON)
        assert "<table>" in html
        assert SEASON in html
        assert "<tbody>" in html

    def test_html_is_valid_document_structure(self) -> None:
        html = _capture_html(RANKINGS, SEASON)
        assert "<!DOCTYPE html>" in html
        assert "<html>" in html
        assert "</html>" in html
        assert "<table>" in html
        assert "</table>" in html

    def test_weasyprint_html_called_with_string_kwarg(self) -> None:
        mock_module = _make_weasyprint_mock()
        with patch.dict(sys.modules, {"weasyprint": mock_module}):
            generate_pdf(RANKINGS, SEASON)
        call_kwargs = mock_module.HTML.call_args.kwargs
        assert "string" in call_kwargs

    def test_write_pdf_called_once(self) -> None:
        mock_module = _make_weasyprint_mock()
        with patch.dict(sys.modules, {"weasyprint": mock_module}):
            generate_pdf(RANKINGS, SEASON)
        mock_module.HTML.return_value.write_pdf.assert_called_once()
