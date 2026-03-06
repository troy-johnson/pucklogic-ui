"""
TDD tests for scrapers/nhl_com.py.

All HTTP and DB I/O is mocked.
Written BEFORE the implementation.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scrapers.nhl_com import NhlComScraper

SEASON = "2025-26"


def _make_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        text=json.dumps(data),
        request=httpx.Request("GET", "http://x"),
    )


def _mock_db(source_id: str = "src-1", player_id: str = "p-1") -> MagicMock:
    db = MagicMock()
    # sources.upsert(...).execute() → {"data": [{"id": source_id}]}
    db.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": source_id}
    ]
    # players.upsert(...).execute() → {"data": [{"id": player_id}]}
    return db


# ---------------------------------------------------------------------------
# Season ID conversion
# ---------------------------------------------------------------------------


class TestSeasonId:
    def test_converts_2025_26(self) -> None:
        assert NhlComScraper._season_id("2025-26") == "20252026"

    def test_converts_2026_27(self) -> None:
        assert NhlComScraper._season_id("2026-27") == "20262027"

    def test_converts_2024_25(self) -> None:
        assert NhlComScraper._season_id("2024-25") == "20242025"

    def test_century_preserved_for_2099_00(self) -> None:
        # Edge: century boundary
        assert NhlComScraper._season_id("2099-00") == "20992000"


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


class TestBuildUrl:
    def test_includes_nhl_stats_base(self) -> None:
        url = NhlComScraper()._build_url(SEASON)
        assert "api.nhle.com" in url

    def test_includes_season_id(self) -> None:
        url = NhlComScraper()._build_url(SEASON)
        assert "20252026" in url

    def test_includes_game_type_regular_season(self) -> None:
        url = NhlComScraper()._build_url(SEASON)
        assert "gameTypeId=2" in url

    def test_pagination_start_zero_by_default(self) -> None:
        url = NhlComScraper()._build_url(SEASON, start=0)
        assert "start=0" in url

    def test_pagination_start_offset(self) -> None:
        url = NhlComScraper()._build_url(SEASON, start=100)
        assert "start=100" in url


# ---------------------------------------------------------------------------
# scrape()
# ---------------------------------------------------------------------------


NHL_PLAYER_1 = {
    "playerId": 8478402,
    "skaterFullName": "Connor McDavid",
    "teamAbbrevs": "EDM",
    "positionCode": "C",
    "points": 100,
}
NHL_PLAYER_2 = {
    "playerId": 8477492,
    "skaterFullName": "Nathan MacKinnon",
    "teamAbbrevs": "COL",
    "positionCode": "C",
    "points": 95,
}


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_count_of_upserted_rows(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            # robots.txt
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            # NHL API page 1 (2 players — less than PAGE_SIZE so no page 2)
            _make_response({"data": [NHL_PLAYER_1, NHL_PLAYER_2], "total": 2}),
        ]
        db = _mock_db()
        db.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "p-1"}
        ]
        scraper = NhlComScraper(http=mock_http)
        count = await scraper.scrape(SEASON, db)
        assert count == 2

    @pytest.mark.asyncio
    async def test_upserts_source_record(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        # sources table upsert was called
        calls = [str(c) for c in db.table.call_args_list]
        assert any("sources" in c for c in calls)

    @pytest.mark.asyncio
    async def test_raises_when_robots_disallows(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.return_value = httpx.Response(
            200,
            text="User-agent: *\nDisallow: /",
            request=httpx.Request("GET", "http://x"),
        )
        from scrapers.base import RobotsDisallowedError

        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        with pytest.raises(RobotsDisallowedError):
            await scraper.scrape(SEASON, db)

    @pytest.mark.asyncio
    async def test_assigns_rank_1_to_first_player(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        # Find the player_rankings upsert call — rank should be 1
        upsert_calls = [
            c for c in db.table.return_value.upsert.call_args_list if "rank" in str(c)
        ]
        assert any("'rank': 1" in str(c) for c in upsert_calls)

    @pytest.mark.asyncio
    async def test_paginates_until_empty_page(self) -> None:
        """Should keep fetching until a page returns fewer items than PAGE_SIZE."""
        PAGE = NhlComScraper.PAGE_SIZE
        full_page = [NHL_PLAYER_1] * PAGE
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            _make_response({"data": full_page, "total": PAGE + 1}),
            _make_response({"data": [NHL_PLAYER_2], "total": PAGE + 1}),
        ]
        db = _mock_db()
        db.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "p-1"}
        ]
        scraper = NhlComScraper(http=mock_http)
        with patch("scrapers.base.asyncio.sleep", new_callable=AsyncMock):
            count = await scraper.scrape(SEASON, db)
        assert count == PAGE + 1

    @pytest.mark.asyncio
    async def test_sleeps_between_pages(self) -> None:
        PAGE = NhlComScraper.PAGE_SIZE
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            _make_response({"data": [NHL_PLAYER_1] * PAGE}),
            _make_response({"data": []}),
        ]
        db = _mock_db()
        db.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "p-1"}
        ]
        scraper = NhlComScraper(http=mock_http)
        sleep_mock = AsyncMock()
        with patch("scrapers.nhl_com.asyncio.sleep", sleep_mock):
            await scraper.scrape(SEASON, db)
        sleep_mock.assert_awaited_once_with(scraper.MIN_DELAY_SECONDS)
