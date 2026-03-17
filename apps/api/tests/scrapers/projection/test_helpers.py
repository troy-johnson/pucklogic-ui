# apps/api/tests/scrapers/projection/test_helpers.py
from __future__ import annotations

from unittest.mock import MagicMock

from scrapers.projection import apply_column_map, upsert_source, fetch_players_and_aliases


class TestApplyColumnMap:
    COLUMN_MAP = {"Goals": "g", "Assists": "a", "PPP": "ppp", "SOG": "sog"}

    def test_maps_known_columns(self) -> None:
        raw = {"Goals": "30", "Assists": "40", "PPP": "20", "SOG": "200"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert result == {"g": 30, "a": 40, "ppp": 20, "sog": 200}

    def test_ignores_unknown_columns(self) -> None:
        raw = {"Goals": "30", "Unknown": "999"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert "Unknown" not in result
        assert result == {"g": 30}

    def test_empty_string_becomes_none_and_is_stripped(self) -> None:
        raw = {"Goals": "", "Assists": "40"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert "g" not in result  # None values stripped
        assert result["a"] == 40

    def test_dash_becomes_none_and_is_stripped(self) -> None:
        raw = {"Goals": "-", "Assists": "10"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert "g" not in result

    def test_decimal_truncated_to_int(self) -> None:
        raw = {"Goals": "29.7"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert result["g"] == 29

    def test_empty_row_returns_empty_dict(self) -> None:
        assert apply_column_map({}, self.COLUMN_MAP) == {}


class TestUpsertSource:
    def test_calls_upsert_on_sources_table(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "src-1"}
        ]
        result = upsert_source(mock_db, "hashtag_hockey", "Hashtag Hockey")
        mock_db.table.assert_called_once_with("sources")
        assert result == "src-1"


class TestFetchPlayersAndAliases:
    def test_returns_players_and_aliases(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        players, aliases = fetch_players_and_aliases(mock_db)
        assert players == []
        assert aliases == []
