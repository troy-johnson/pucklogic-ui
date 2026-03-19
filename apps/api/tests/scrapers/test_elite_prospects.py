"""TDD tests for scrapers/elite_prospects.py. All HTTP and DB I/O is mocked."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scrapers.elite_prospects import EliteProspectsScraper

FIXTURE = Path(__file__).parent / "fixtures" / "elite_prospects_sample.json"
SEASON = "2024-25"

_PLAYERS = [
    {"id": "p-mcdavid", "name": "Connor McDavid"},
    {"id": "p-michkov", "name": "Matvei Michkov"},
    {"id": "p-hischier", "name": "Nico Hischier"},
]
_ALIASES: list[dict] = []


def _make_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=json.dumps(data), request=httpx.Request("GET", "http://x"))


def _mock_db() -> MagicMock:
    """Minimal DB mock — all TestScrape tests patch _fetch_players/_fetch_aliases directly."""
    db = MagicMock()
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
    return db


# ---------------------------------------------------------------------------
# Season helpers
# ---------------------------------------------------------------------------


class TestSeasonHelpers:
    def test_season_slug_2024_25(self) -> None:
        assert EliteProspectsScraper._season_slug("2024-25") == "2024-2025"

    def test_season_slug_2005_06(self) -> None:
        assert EliteProspectsScraper._season_slug("2005-06") == "2005-2006"

    def test_season_end_year(self) -> None:
        assert EliteProspectsScraper._season_end_year("2024-25") == 2025


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    def setup_method(self) -> None:
        self.data = json.loads(FIXTURE.read_text())["data"]

    def test_returns_three_rows(self) -> None:
        assert len(EliteProspectsScraper._parse_response(self.data, 2025)) == 3

    def test_elc_flag_true_for_elc(self) -> None:
        rows = EliteProspectsScraper._parse_response(self.data, 2025)
        michkov = next(r for r in rows if "Michkov" in r["player_name"])
        assert michkov["elc_flag"] is True

    def test_elc_flag_false_for_spc(self) -> None:
        rows = EliteProspectsScraper._parse_response(self.data, 2025)
        assert not next(r for r in rows if "McDavid" in r["player_name"])["elc_flag"]

    def test_contract_year_true_when_expiry_matches(self) -> None:
        rows = EliteProspectsScraper._parse_response(self.data, 2025)
        assert next(r for r in rows if "Hischier" in r["player_name"])["contract_year_flag"]

    def test_contract_year_false_when_expiry_after_season(self) -> None:
        rows = EliteProspectsScraper._parse_response(self.data, 2025)
        assert not next(r for r in rows if "McDavid" in r["player_name"])["contract_year_flag"]

    def test_missing_contract_defaults_to_false(self) -> None:
        rows = EliteProspectsScraper._parse_response(
            [{"player": {"firstName": "Test", "lastName": "Player"}}], 2025
        )
        assert rows[0]["elc_flag"] is False
        assert rows[0]["contract_year_flag"] is False


# ---------------------------------------------------------------------------
# scrape()
# ---------------------------------------------------------------------------


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_upserted_count(self) -> None:
        scraper = EliteProspectsScraper(api_key="test-key")
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
            assert await scraper.scrape(SEASON, _mock_db()) == 3

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self) -> None:
        scraper = EliteProspectsScraper(api_key="")
        with pytest.raises(ValueError, match="ELITE_PROSPECTS_API_KEY"):
            await scraper.scrape(SEASON, _mock_db())

    @pytest.mark.asyncio
    async def test_robots_disallowed_raises(self) -> None:
        from scrapers.base import RobotsDisallowedError

        scraper = EliteProspectsScraper(api_key="key")
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape(SEASON, _mock_db())

    @pytest.mark.asyncio
    async def test_unmatched_player_skipped(self) -> None:
        scraper = EliteProspectsScraper(api_key="key")
        db = _mock_db()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=_make_response(json.loads(FIXTURE.read_text()))),
            ),
            patch.object(scraper, "_fetch_players", return_value=[]),
            patch.object(scraper, "_fetch_aliases", return_value=[]),
        ):
            count = await scraper.scrape(SEASON, db)
        db.table.return_value.upsert.assert_not_called()
        assert count == 0

    @pytest.mark.asyncio
    async def test_paginates(self) -> None:
        scraper = EliteProspectsScraper(api_key="key")
        p1 = {
            "data": [{"player": {"firstName": "A", "lastName": "B"}}],
            "total": 2,
            "limit": 1,
            "offset": 0,
        }
        p2 = {
            "data": [{"player": {"firstName": "C", "lastName": "D"}}],
            "total": 2,
            "limit": 1,
            "offset": 1,
        }
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(side_effect=[_make_response(p1), _make_response(p2)]),
            ),
            patch.object(
                scraper,
                "_fetch_players",
                return_value=[{"id": "p1", "name": "A B"}, {"id": "p2", "name": "C D"}],
            ),
            patch.object(scraper, "_fetch_aliases", return_value=[]),
        ):
            assert await scraper.scrape(SEASON, _mock_db()) == 2
