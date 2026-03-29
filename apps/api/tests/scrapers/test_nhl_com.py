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

from scrapers.nhl_com import NhlComScraper, _iter_seasons

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
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": source_id}]
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


class TestIterSeasons:
    def test_returns_inclusive_history_range(self) -> None:
        assert _iter_seasons("2005-06", "2007-08") == ["2005-06", "2006-07", "2007-08"]

    def test_raises_when_start_is_after_end(self) -> None:
        with pytest.raises(ValueError, match="start season"):
            _iter_seasons("2007-08", "2005-06")


class TestPlayerStatsUpsertBehavior:
    def test_summary_upsert_uses_default_to_null_false(self) -> None:
        scraper = NhlComScraper()
        db = MagicMock()

        scraper._upsert_player_stats(
            db,
            player_id="player-1",
            season="2009-10",
            player={
                "gamesPlayed": 82,
                "goals": 30,
                "assists": 50,
                "points": 80,
                "ppPoints": 20,
                "shPoints": 2,
                "shots": 250,
                "faceoffWinPct": 52.4,
            },
        )

        db.table.assert_called_once_with("player_stats")
        _, kwargs = db.table.return_value.upsert.call_args
        assert kwargs["on_conflict"] == "player_id,season"
        assert kwargs["default_to_null"] is False

    def test_realtime_upsert_uses_default_to_null_false(self) -> None:
        scraper = NhlComScraper()
        db = MagicMock()

        did_upsert = scraper._upsert_realtime_stats(
            db,
            player_id="player-1",
            season="2024-25",
            player={"hits": 120, "blockedShots": 65},
        )

        assert did_upsert is True
        _, kwargs = db.table.return_value.upsert.call_args
        assert kwargs["on_conflict"] == "player_id,season"
        assert kwargs["default_to_null"] is False


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
    "goals": 52,
    "assists": 89,
    "gamesPlayed": 82,
}
NHL_PLAYER_2 = {
    "playerId": 8477492,
    "skaterFullName": "Nathan MacKinnon",
    "teamAbbrevs": "COL",
    "positionCode": "C",
    "points": 95,
    "goals": 45,
    "assists": 79,
    "gamesPlayed": 80,
}
NHL_REALTIME_PLAYER_1 = {
    "playerId": 8478402,  # same ID as NHL_PLAYER_1 (McDavid)
    "hits": 34,
    "blockedShots": 12,
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
            # realtime page 1 (empty — no realtime data needed for this test)
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
        scraper = NhlComScraper(http=mock_http)
        summary_count, realtime_count = await scraper.scrape(SEASON, db)
        assert summary_count == 2
        assert realtime_count == 0

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
            # realtime page 1 (empty)
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
            # realtime page 1 (empty)
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        # Find the player_rankings upsert call — rank should be 1
        upsert_calls = [c for c in db.table.return_value.upsert.call_args_list if "rank" in str(c)]
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
            # realtime page 1 (empty)
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
        scraper = NhlComScraper(http=mock_http)
        with patch("scrapers.base.asyncio.sleep", new_callable=AsyncMock):
            summary_count, realtime_count = await scraper.scrape(SEASON, db)
        assert summary_count == PAGE + 1
        assert realtime_count == 0

    @pytest.mark.asyncio
    async def test_upserts_goals_and_gp_to_player_stats(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            # realtime page 1 (empty)
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        tables_written = [str(c) for c in db.table.call_args_list]
        assert any("player_stats" in t for t in tables_written)

    @pytest.mark.asyncio
    async def test_player_stats_payload_contains_gp(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            # realtime page 1 (empty)
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'gp': 82" in upsert_calls

    @pytest.mark.asyncio
    async def test_player_stats_payload_contains_goals(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            # realtime page 1 (empty)
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'g': 52" in upsert_calls
        assert "'a': 89" in upsert_calls

    @pytest.mark.asyncio
    async def test_player_stats_skips_when_gp_missing(self) -> None:
        """Players without gamesPlayed should not trigger a player_stats upsert."""
        player_no_gp = {
            "playerId": 9999999,
            "skaterFullName": "Unknown Player",
            "teamAbbrevs": "UNK",
            "positionCode": "C",
            "points": 0,
        }
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                request=httpx.Request("GET", "http://x"),
            ),
            _make_response({"data": [player_no_gp], "total": 1}),
            # realtime page 1 (empty — player_no_gp has no realtime data either)
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        tables_written = [str(c) for c in db.table.call_args_list]
        assert not any("player_stats" in t for t in tables_written)

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
            # realtime page 1 (empty — no sleep in realtime loop)
            _make_response({"data": [], "total": 0}),
        ]
        db = _mock_db()
        db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
        scraper = NhlComScraper(http=mock_http)
        sleep_mock = AsyncMock()
        with patch("scrapers.nhl_com.asyncio.sleep", sleep_mock):
            await scraper.scrape(SEASON, db)
        sleep_mock.assert_awaited_once_with(scraper.MIN_DELAY_SECONDS)


class TestRealtimeEndpoint:
    def test_build_realtime_url_contains_realtime_path(self) -> None:
        url = NhlComScraper()._build_realtime_url(SEASON)
        assert "skater/realtime" in url

    @pytest.mark.asyncio
    async def test_upserts_hits_and_blocks(self) -> None:
        """Two-pass scrape: summary then realtime. Hits/blocks land in player_stats."""
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            # robots.txt
            httpx.Response(
                200, text="User-agent: *\nAllow: /", request=httpx.Request("GET", "http://x")
            ),
            # summary page 1 (less than PAGE_SIZE → done)
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            # realtime page 1
            _make_response({"data": [NHL_REALTIME_PLAYER_1], "total": 1}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'hits': 34" in upsert_calls
        assert "'blocks': 12" in upsert_calls

    @pytest.mark.asyncio
    async def test_realtime_falls_back_to_db_when_player_not_in_summary(self) -> None:
        """Realtime player absent from summary should fall back to DB lookup by nhl_id."""
        realtime_unknown = {"playerId": 9999999, "hits": 100, "blockedShots": 50}
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200, text="User-agent: *\nAllow: /", request=httpx.Request("GET", "http://x")
            ),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            _make_response({"data": [realtime_unknown], "total": 1}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        with patch.object(scraper, "_lookup_player_by_nhl_id", return_value="p-db") as lookup:
            await scraper.scrape(SEASON, db)
        lookup.assert_called_once_with(db, "9999999")
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'player_id': 'p-db'" in upsert_calls
        assert "'hits': 100" in upsert_calls
        assert "'blocks': 50" in upsert_calls

    @pytest.mark.asyncio
    async def test_realtime_skips_when_no_hits_or_blocks(self) -> None:
        """Realtime row with neither hits nor blockedShots should not trigger upsert."""
        realtime_empty = {"playerId": 8478402}  # no hits, no blockedShots
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200, text="User-agent: *\nAllow: /", request=httpx.Request("GET", "http://x")
            ),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            _make_response({"data": [realtime_empty], "total": 1}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'hits'" not in upsert_calls


# ---------------------------------------------------------------------------
# Aggregate URL / traded-player fixes  (Phase 1a)
# ---------------------------------------------------------------------------


class TestAggregateUrl:
    def test_build_url_uses_aggregate_true(self) -> None:
        url = NhlComScraper()._build_url(SEASON)
        assert "isAggregate=true" in url

    def test_build_realtime_url_uses_aggregate_true(self) -> None:
        url = NhlComScraper()._build_realtime_url(SEASON)
        assert "isAggregate=true" in url

    def test_traded_player_team_stored_as_last_team(self) -> None:
        """teamAbbrevs comma list → last team stored in players.team."""
        traded_player = {
            "playerId": 8480802,
            "skaterFullName": "Ryan McLeod",
            "teamAbbrevs": "TOR,BUF",
            "positionCode": "C",
            "gamesPlayed": 73,
            "goals": 12,
            "assists": 20,
            "points": 32,
            "ppPoints": 5,
            "shPoints": 0,
            "shots": 84,
        }
        scraper = NhlComScraper()
        db = _mock_db()
        scraper._upsert_player(db, traded_player)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'team': 'BUF'" in upsert_calls
        assert "TOR,BUF" not in upsert_calls

    def test_single_team_player_unaffected(self) -> None:
        """Non-traded player with single teamAbbrevs stored as-is."""
        scraper = NhlComScraper()
        db = _mock_db()
        scraper._upsert_player(db, NHL_PLAYER_1)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'team': 'EDM'" in upsert_calls


# ---------------------------------------------------------------------------
# Realtime fallback by nhl_id  (Phase 1b)
# ---------------------------------------------------------------------------


class TestRealtimeFallback:
    """Realtime pass: players not in nhl_id_map fall back to DB lookup by nhl_id."""

    def _make_db_with_fallback(self, player_id: str = "p-fallback") -> MagicMock:
        db = MagicMock()
        db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": player_id}]
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": player_id}
        ]
        return db

    def _make_db_no_fallback(self) -> MagicMock:
        db = MagicMock()
        db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        return db

    @pytest.mark.asyncio
    async def test_realtime_fallback_looks_up_by_nhl_id(self) -> None:
        """Player not in nhl_id_map is found via DB lookup → hits/blocks written."""
        defensive_player = {"playerId": 8476441, "hits": 120, "blockedShots": 85}
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200, text="User-agent: *\nAllow: /", request=httpx.Request("GET", "http://x")
            ),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            _make_response({"data": [NHL_REALTIME_PLAYER_1, defensive_player], "total": 2}),
        ]
        db = self._make_db_with_fallback(player_id="p-edmundson")
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'hits': 120" in upsert_calls
        assert "'blocks': 85" in upsert_calls

    @pytest.mark.asyncio
    async def test_realtime_skips_when_not_in_map_or_db(self) -> None:
        """Player not in nhl_id_map AND not in DB → skipped cleanly."""
        truly_unknown = {"playerId": 9999999, "hits": 100, "blockedShots": 50}
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(
                200, text="User-agent: *\nAllow: /", request=httpx.Request("GET", "http://x")
            ),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            _make_response({"data": [truly_unknown], "total": 1}),
        ]
        db = self._make_db_no_fallback()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'hits': 100" not in upsert_calls
