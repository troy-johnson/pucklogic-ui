# apps/api/tests/scrapers/test_schedule_scores.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from scrapers.schedule_scores import (
    compute_schedule_score,
    count_off_night_games,
)

# Sample games — player in games on dates with varying team counts
GAMES = [
    {"date": "2025-10-07", "teams": ["EDM", "TOR", "VAN", "MTL"]},   # 4 teams playing
    {"date": "2025-10-08", "teams": ["EDM", "TOR"]},                  # 2 teams — off-night
    {"date": "2025-10-09", "teams": ["EDM", "TOR", "VAN", "MTL",
                                      "CGY", "WPG", "MIN", "DAL",
                                      "NYR", "BOS", "PHI", "PIT",
                                      "DET", "CAR", "FLA", "TBL"]},   # 16 teams — not off-night
]

# Player plays for EDM — appears in all 3 dates above
PLAYER_GAME_DATES = {"2025-10-07", "2025-10-08", "2025-10-09"}


class TestCountOffNightGames:
    def test_counts_games_with_few_teams(self) -> None:
        # Off-night = ≤ 10 teams playing that day
        count = count_off_night_games(PLAYER_GAME_DATES, GAMES, off_night_threshold=10)
        # 2025-10-07 has 4 teams → off-night; 2025-10-08 has 2 → off-night; 2025-10-09 has 16 → not
        assert count == 2

    def test_zero_when_all_busy_nights(self) -> None:
        busy_dates = {"2025-10-09"}
        count = count_off_night_games(busy_dates, GAMES, off_night_threshold=10)
        assert count == 0

    def test_empty_dates_returns_zero(self) -> None:
        assert count_off_night_games(set(), GAMES) == 0


class TestComputeScheduleScore:
    def test_normalized_between_0_and_1(self) -> None:
        score = compute_schedule_score(off_night_games=5, total_games=82)
        assert 0.0 <= score <= 1.0

    def test_more_off_night_games_higher_score(self) -> None:
        low = compute_schedule_score(off_night_games=2, total_games=82)
        high = compute_schedule_score(off_night_games=20, total_games=82)
        assert high > low

    def test_zero_total_games_returns_zero(self) -> None:
        assert compute_schedule_score(0, 0) == 0.0


async def test_ingest_aborts_on_empty_schedule() -> None:
    """ingest() must not upsert any rows when _fetch_season_schedule returns []."""
    from scrapers.schedule_scores import ingest

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.execute.return_value.data = [
        {"id": "p1", "team": "EDM"},
    ]

    with patch(
        "scrapers.schedule_scores._fetch_season_schedule",
        new=AsyncMock(return_value=[]),
    ):
        await ingest("2025-26", mock_db)

    mock_db.table.return_value.upsert.assert_not_called()
