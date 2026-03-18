# apps/api/tests/scrapers/test_platform_positions.py
from __future__ import annotations

from unittest.mock import MagicMock

from scrapers.platform_positions import (
    map_espn_positions,
    upsert_platform_positions,
)

ESPN_PLAYER = {
    "id": 3068,
    "fullName": "Connor McDavid",
    "defaultPositionId": 1,
    "eligibleSlots": [1, 2, 5],  # C, F, UTIL
}

PLAYERS_DB = [
    {"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"},
    {"id": "p2", "name": "Leon Draisaitl", "nhl_id": "8477934"},
]


class TestMapEspnPositions:
    def test_maps_center_slot(self) -> None:
        result = map_espn_positions([1, 2, 5])
        assert "C" in result

    def test_excludes_bench_slot(self) -> None:
        result = map_espn_positions([7])  # BN
        assert result == []

    def test_deduplicates_positions(self) -> None:
        result = map_espn_positions([1, 1, 2])
        assert result.count("C") == 1


class TestUpsertPlatformPositions:
    def test_calls_upsert_on_correct_table(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = []
        upsert_platform_positions(mock_db, "p1", "espn", ["C", "F"])
        mock_db.table.assert_called_with("player_platform_positions")

    def test_passes_player_id_platform_positions(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = []
        upsert_platform_positions(mock_db, "p1", "espn", ["C", "LW"])
        call_kwargs = mock_db.table.return_value.upsert.call_args
        data = call_kwargs.args[0]
        assert data["player_id"] == "p1"
        assert data["platform"] == "espn"
        assert set(data["positions"]) == {"C", "LW"}
