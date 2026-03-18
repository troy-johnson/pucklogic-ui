# apps/api/tests/scrapers/test_nst.py
"""
TDD tests for scrapers/nst.py.

All HTTP and DB I/O is mocked.
Written BEFORE the implementation (red-green-refactor).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.nst import NstScraper

FIXTURE = Path(__file__).parent / "fixtures" / "nst_skaters.html"


# ---------------------------------------------------------------------------
# _parse_html
# ---------------------------------------------------------------------------


class TestParseHtml:
    def test_returns_list(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_each_row_has_player_name(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        for row in rows:
            assert "player_name" in row
            assert row["player_name"]

    def test_parses_numeric_stats(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        # At least one row should have stat keys beyond player_name
        rows_with_stats = [r for r in rows if len(r) > 1]
        assert len(rows_with_stats) > 0

    def test_parses_cf_pct(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "cf_pct" in row
        assert isinstance(row["cf_pct"], float)
        assert row["cf_pct"] == pytest.approx(58.3)

    def test_parses_xgf_pct(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "xgf_pct" in row
        assert isinstance(row["xgf_pct"], float)
        assert row["xgf_pct"] == pytest.approx(59.1)

    def test_parses_sh_pct(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "sh_pct" in row
        assert isinstance(row["sh_pct"], float)
        assert row["sh_pct"] == pytest.approx(14.2)

    def test_parses_pdo(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "pdo" in row
        assert isinstance(row["pdo"], float)
        assert row["pdo"] == pytest.approx(101.5)

    def test_parses_toi(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "toi_per_game" in row
        assert isinstance(row["toi_per_game"], float)
        # TOI / GP = 1640.5 / 82 ≈ 20.0
        assert row["toi_per_game"] == pytest.approx(1640.5 / 82, rel=1e-3)

    def test_parses_gp(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "gp" in row
        assert row["gp"] == 82

    def test_returns_three_rows_for_fixture(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert len(rows) == 3

    def test_empty_table_returns_empty_list(self) -> None:
        html = (
            "<html><body>"
            "<table id='players'>"
            "<thead><tr><th>Player</th></tr></thead>"
            "<tbody></tbody>"
            "</table></body></html>"
        )
        rows = NstScraper._parse_html(html)
        assert rows == []

    def test_missing_table_returns_empty_list(self) -> None:
        rows = NstScraper._parse_html("<html><body><p>no table</p></body></html>")
        assert rows == []


# ---------------------------------------------------------------------------
# _season_id
# ---------------------------------------------------------------------------


class TestSeasonId:
    def test_converts_season_format(self) -> None:
        assert NstScraper._season_id("2024-25") == "20242025"

    def test_handles_2000s(self) -> None:
        assert NstScraper._season_id("2025-26") == "20252026"

    def test_handles_2026_27(self) -> None:
        assert NstScraper._season_id("2026-27") == "20262027"


# ---------------------------------------------------------------------------
# scrape()
# ---------------------------------------------------------------------------


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_int(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        html = FIXTURE.read_text()
        scraper = NstScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=MagicMock(text=html)),
            ),
        ):
            count = await scraper.scrape("2025-26", mock_db)
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_raises_on_robots_disallow(self) -> None:
        from scrapers.base import RobotsDisallowedError

        mock_db = MagicMock()
        scraper = NstScraper()
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape("2025-26", mock_db)

    @pytest.mark.asyncio
    async def test_upserts_player_stats_rows(self) -> None:
        mock_db = MagicMock()

        # _fetch_players returns players list; _fetch_aliases returns empty list.
        # Use side_effect on table() so each call to table("players") vs
        # table("player_aliases") can return different data.
        players_mock = MagicMock()
        players_mock.select.return_value.execute.return_value.data = [
            {"id": "player-uuid", "name": "Connor McDavid"},
            {"id": "player-uuid2", "name": "Leon Draisaitl"},
            {"id": "player-uuid3", "name": "Nathan MacKinnon"},
        ]
        aliases_mock = MagicMock()
        aliases_mock.select.return_value.execute.return_value.data = []

        stats_mock = MagicMock()
        stats_mock.upsert.return_value.execute.return_value.data = [{"id": "stat-uuid"}]

        def table_side_effect(name: str) -> MagicMock:
            if name == "players":
                return players_mock
            if name == "player_aliases":
                return aliases_mock
            if name == "player_stats":
                return stats_mock
            return MagicMock()

        mock_db.table.side_effect = table_side_effect

        html = FIXTURE.read_text()
        scraper = NstScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=MagicMock(text=html)),
            ),
        ):
            count = await scraper.scrape("2025-26", mock_db)
        # All three players match by exact name — all should be upserted.
        assert count == 3
        assert stats_mock.upsert.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_html(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        scraper = NstScraper()
        empty_html = "<html><body></body></html>"
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=MagicMock(text=empty_html)),
            ),
        ):
            count = await scraper.scrape("2025-26", mock_db)
        assert count == 0
