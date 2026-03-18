# apps/api/tests/scrapers/projection/test_yahoo.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scrapers.projection.yahoo import YahooScraper

# Mock Yahoo API player data shape
YAHOO_PLAYER_1 = {
    "player_id": "3981",
    "name": {"full": "Connor McDavid"},
    "display_position": "C",
    "eligible_positions": [{"position": "C"}],
    "player_stats": {
        "stats": [
            {"stat_id": "1", "value": "52"},   # GP
            {"stat_id": "5", "value": "45"},   # G
            {"stat_id": "6", "value": "72"},   # A
        ]
    },
}

YAHOO_PLAYER_2 = {
    "player_id": "6370",
    "name": {"full": "Leon Draisaitl"},
    "display_position": "C",
    "eligible_positions": [{"position": "C"}, {"position": "LW"}],
    "player_stats": {
        "stats": [
            {"stat_id": "1", "value": "82"},
            {"stat_id": "5", "value": "40"},
            {"stat_id": "6", "value": "65"},
        ]
    },
}


class TestParsePlayerRow:
    def test_extracts_player_name(self) -> None:
        result = YahooScraper._parse_player(YAHOO_PLAYER_1)
        assert result["player_name"] == "Connor McDavid"

    def test_maps_goals_stat(self) -> None:
        result = YahooScraper._parse_player(YAHOO_PLAYER_1)
        assert result.get("g") == 45

    def test_maps_assists_stat(self) -> None:
        result = YahooScraper._parse_player(YAHOO_PLAYER_1)
        assert result.get("a") == 72

    def test_missing_stat_returns_none(self) -> None:
        # YAHOO_PLAYER_1 has no PPP stat — should be absent from result
        result = YahooScraper._parse_player(YAHOO_PLAYER_1)
        assert result.get("ppp") is None


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_int_count(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []

        scraper = YahooScraper()
        players = [YAHOO_PLAYER_1, YAHOO_PLAYER_2]
        with patch.object(scraper, "_fetch_yahoo_players", return_value=players):
            count = await scraper.scrape("2025-26", mock_db)
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_skips_when_no_oauth_token(self) -> None:
        from core.config import settings
        original = settings.yahoo_oauth_refresh_token
        settings.yahoo_oauth_refresh_token = ""
        try:
            mock_db = MagicMock()
            count = await YahooScraper().scrape("2025-26", mock_db)
            assert count == 0
        finally:
            settings.yahoo_oauth_refresh_token = original
