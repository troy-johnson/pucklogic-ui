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
        from core.config import settings

        # Per-table mock responses
        players_data = [{"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"}]
        aliases_data: list[dict] = []

        def make_table_mock(table_name: str) -> MagicMock:
            tbl = MagicMock()
            if table_name == "sources":
                tbl.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
                tbl.update.return_value.eq.return_value.execute.return_value.data = []
            elif table_name == "players":
                tbl.select.return_value.execute.return_value.data = players_data
            elif table_name == "player_aliases":
                tbl.select.return_value.execute.return_value.data = aliases_data
            elif table_name == "player_projections":
                tbl.upsert.return_value.execute.return_value.data = []
            else:
                tbl.insert.return_value.execute.return_value.data = []
                tbl.upsert.return_value.execute.return_value.data = []
            return tbl

        mock_db = MagicMock()
        mock_db.table.side_effect = make_table_mock

        original = settings.yahoo_oauth_refresh_token
        settings.yahoo_oauth_refresh_token = "fake-token"
        try:
            scraper = YahooScraper()
            with patch.object(
                scraper, "_fetch_yahoo_players", return_value=[YAHOO_PLAYER_1, YAHOO_PLAYER_2]
            ):
                count = await scraper.scrape("2025-26", mock_db)
        finally:
            settings.yahoo_oauth_refresh_token = original
        assert isinstance(count, int)
        assert count >= 1  # at least McDavid should match

    async def test_scrape_checks_robots_txt(self, monkeypatch) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []

        scraper = YahooScraper()
        robots_calls: list[str] = []

        async def fake_check_robots(url: str) -> bool:
            robots_calls.append(url)
            return True

        monkeypatch.setattr("core.config.settings.yahoo_oauth_refresh_token", "tok")
        monkeypatch.setattr(scraper, "_check_robots_txt", fake_check_robots)
        with patch.object(scraper, "_fetch_yahoo_players", return_value=[]):
            await scraper.scrape("2025-26", mock_db)

        assert len(robots_calls) == 1, "Expected _check_robots_txt to be called once"

    async def test_skips_when_no_oauth_token(self, monkeypatch) -> None:
        monkeypatch.setattr("core.config.settings.yahoo_oauth_refresh_token", "")
        mock_db = MagicMock()
        count = await YahooScraper().scrape("2025-26", mock_db)
        assert count == 0


def test_fetch_yahoo_players_uses_pagination(monkeypatch) -> None:
    """fetch_all_yahoo_nhl_players must paginate via player_stats(), not player_details('all')."""
    import sys
    import types

    player_stats_calls: list[dict] = []
    player_details_calls: list = []

    class FakeLeague:
        def player_details(self, arg):
            player_details_calls.append(arg)
            return []

    class FakeGame:
        def league_ids(self):
            return ["12345"]
        def to_league(self, lid):
            return FakeLeague()
        def player_stats(self, ids, req_type="season", start=0, count=25):
            player_stats_calls.append({"start": start, "count": count})
            return []  # empty → pagination loop exits immediately

    fake_yfa = types.ModuleType("yahoo_fantasy_api")
    fake_yfa.OAuth2 = lambda *a, **kw: MagicMock()  # type: ignore[attr-defined]
    fake_yfa.Game = lambda *a, **kw: FakeGame()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yahoo_fantasy_api", fake_yfa)

    from scrapers.projection.yahoo import fetch_all_yahoo_nhl_players
    fetch_all_yahoo_nhl_players("tok")

    assert len(player_stats_calls) >= 1, "Expected player_stats() to be called for pagination"
    assert "all" not in player_details_calls, "Must not use player_details('all') name-search"
