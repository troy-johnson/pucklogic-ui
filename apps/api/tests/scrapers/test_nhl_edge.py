"""TDD tests for scrapers/nhl_edge.py. All HTTP and DB I/O is mocked."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scrapers.nhl_edge import NhlEdgeScraper

FIXTURE = Path(__file__).parent / "fixtures" / "nhl_edge_sample.json"
SEASON = "2024-25"

_PLAYERS = [
    {"id": "p-mcdavid", "name": "Connor McDavid"},
    {"id": "p-mackinnon", "name": "Nathan MacKinnon"},
]
_ALIASES: list[dict] = []


def _make_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=json.dumps(data), request=httpx.Request("GET", "http://x"))


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
    return db


class TestSeasonId:
    def test_2024_25(self) -> None:
        assert NhlEdgeScraper._season_id("2024-25") == "20242025"

    def test_2005_06(self) -> None:
        assert NhlEdgeScraper._season_id("2005-06") == "20052006"


class TestParseResponse:
    def test_returns_two_rows(self) -> None:
        data = json.loads(FIXTURE.read_text())["data"]
        assert len(NhlEdgeScraper._parse_response(data)) == 2

    def test_parses_speed_bursts(self) -> None:
        rows = NhlEdgeScraper._parse_response(json.loads(FIXTURE.read_text())["data"])
        mcdavid = next(r for r in rows if "McDavid" in r["player_name"])
        assert mcdavid["speed_bursts_22"] == pytest.approx(3.2)

    def test_parses_top_speed(self) -> None:
        rows = NhlEdgeScraper._parse_response(json.loads(FIXTURE.read_text())["data"])
        mcdavid = next(r for r in rows if "McDavid" in r["player_name"])
        assert mcdavid["top_speed"] == pytest.approx(25.4)

    def test_skips_row_with_no_name(self) -> None:
        assert NhlEdgeScraper._parse_response([{"playerName": ""}]) == []


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_count(self) -> None:
        scraper = NhlEdgeScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=_make_response(json.loads(FIXTURE.read_text()))),
            ),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            assert await scraper.scrape(SEASON, _mock_db()) == 2

    @pytest.mark.asyncio
    async def test_robots_disallowed_raises(self) -> None:
        from scrapers.base import RobotsDisallowedError

        scraper = NhlEdgeScraper()
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape(SEASON, _mock_db())

    @pytest.mark.asyncio
    async def test_upserts_speed_columns(self) -> None:
        scraper = NhlEdgeScraper()
        upserted: list[dict] = []

        def capture(payload, on_conflict=None):
            upserted.append(payload)
            m = MagicMock()
            m.execute.return_value.data = [{"id": "p-1"}]
            return m

        db = _mock_db()
        db.table.return_value.upsert.side_effect = capture

        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=_make_response(json.loads(FIXTURE.read_text()))),
            ),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            await scraper.scrape(SEASON, db)

        assert any("speed_bursts_22" in p for p in upserted)
        assert any("top_speed" in p for p in upserted)
