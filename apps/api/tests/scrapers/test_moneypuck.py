"""
TDD tests for scrapers/moneypuck.py.

All HTTP and DB I/O is mocked.
Written BEFORE the implementation.
"""
from __future__ import annotations

import textwrap
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scrapers.moneypuck import MoneyPuckScraper

SEASON = "2025-26"

# Minimal CSV matching the columns the scraper cares about
SKATERS_CSV = textwrap.dedent("""\
    playerId,name,team,position,situation,I_F_xGoals
    8478402,Connor McDavid,EDM,C,all,45.3
    8477492,Nathan MacKinnon,COL,C,all,40.1
    9999999,Leon Draisaitl,EDM,C,all,38.7
""")

# A row that should be SKIPPED because situation != "all"
SKATERS_CSV_MIXED = textwrap.dedent("""\
    playerId,name,team,position,situation,I_F_xGoals
    8478402,Connor McDavid,EDM,C,all,45.3
    8478402,Connor McDavid,EDM,C,5v5,20.1
    8477492,Nathan MacKinnon,COL,C,all,40.1
""")


def _make_response(text: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=text, request=httpx.Request("GET", "http://x"))


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "x-1"}]
    return db


# ---------------------------------------------------------------------------
# Season year conversion
# ---------------------------------------------------------------------------


class TestSeasonYear:
    def test_converts_2025_26(self) -> None:
        assert MoneyPuckScraper._season_year("2025-26") == "2025"

    def test_converts_2024_25(self) -> None:
        assert MoneyPuckScraper._season_year("2024-25") == "2024"

    def test_converts_2026_27(self) -> None:
        assert MoneyPuckScraper._season_year("2026-27") == "2026"


# ---------------------------------------------------------------------------
# CSV URL
# ---------------------------------------------------------------------------


class TestCsvUrl:
    def test_includes_moneypuck_domain(self) -> None:
        url = MoneyPuckScraper._csv_url("2025-26")
        assert "moneypuck.com" in url

    def test_includes_start_year(self) -> None:
        url = MoneyPuckScraper._csv_url("2025-26")
        assert "2025" in url

    def test_url_ends_with_csv(self) -> None:
        url = MoneyPuckScraper._csv_url("2025-26")
        assert url.endswith(".csv")


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


class TestParseCsv:
    def test_returns_one_row_per_player(self) -> None:
        rows = MoneyPuckScraper._parse_csv(SKATERS_CSV)
        assert len(rows) == 3

    def test_filters_out_non_all_situations(self) -> None:
        rows = MoneyPuckScraper._parse_csv(SKATERS_CSV_MIXED)
        assert len(rows) == 2

    def test_row_has_required_keys(self) -> None:
        rows = MoneyPuckScraper._parse_csv(SKATERS_CSV)
        row = rows[0]
        assert "player_id" in row
        assert "name" in row
        assert "team" in row
        assert "position" in row
        assert "xgoals" in row

    def test_players_sorted_descending_by_xgoals(self) -> None:
        rows = MoneyPuckScraper._parse_csv(SKATERS_CSV)
        xgoals = [r["xgoals"] for r in rows]
        assert xgoals == sorted(xgoals, reverse=True)

    def test_player_id_extracted_correctly(self) -> None:
        rows = MoneyPuckScraper._parse_csv(SKATERS_CSV)
        assert rows[0]["player_id"] == "8478402"

    def test_empty_csv_returns_empty_list(self) -> None:
        header_only = "playerId,name,team,position,situation,I_F_xGoals\n"
        assert MoneyPuckScraper._parse_csv(header_only) == []


# ---------------------------------------------------------------------------
# scrape()
# ---------------------------------------------------------------------------


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_count_of_upserted_rows(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            _make_response("User-agent: *\nAllow: /"),   # robots.txt
            _make_response(SKATERS_CSV),                  # CSV
        ]
        db = _mock_db()
        scraper = MoneyPuckScraper(http=mock_http)
        count = await scraper.scrape(SEASON, db)
        assert count == 3

    @pytest.mark.asyncio
    async def test_assigns_rank_1_to_highest_xgoals(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            _make_response("User-agent: *\nAllow: /"),
            _make_response(SKATERS_CSV),
        ]
        db = _mock_db()
        scraper = MoneyPuckScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = [
            c for c in db.table.return_value.upsert.call_args_list
            if "rank" in str(c)
        ]
        assert any("'rank': 1" in str(c) for c in upsert_calls)

    @pytest.mark.asyncio
    async def test_raises_when_robots_disallows(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.return_value = _make_response("User-agent: *\nDisallow: /")
        from scrapers.base import RobotsDisallowedError
        db = _mock_db()
        scraper = MoneyPuckScraper(http=mock_http)
        with pytest.raises(RobotsDisallowedError):
            await scraper.scrape(SEASON, db)

    @pytest.mark.asyncio
    async def test_upserts_source_record(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            _make_response("User-agent: *\nAllow: /"),
            _make_response(SKATERS_CSV),
        ]
        db = _mock_db()
        scraper = MoneyPuckScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        calls = [str(c) for c in db.table.call_args_list]
        assert any("sources" in c for c in calls)

    @pytest.mark.asyncio
    async def test_fetches_correct_season_csv(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            _make_response("User-agent: *\nAllow: /"),
            _make_response(SKATERS_CSV),
        ]
        db = _mock_db()
        scraper = MoneyPuckScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        csv_url = mock_http.get.call_args_list[1].args[0]
        assert "2025" in csv_url
