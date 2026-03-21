"""
Smoke test: NhlComScraper

Verifies that the NHL.com scraper writes gp, g, and a columns to player_stats
and correctly upserts player rows.  This test also serves as the prerequisite
seed step for all other smoke tests via the ``nhl_com_done`` session fixture.

Live endpoint: https://api.nhle.com/stats/rest/en/skater/summary
"""

from __future__ import annotations

from typing import Any

from tests.smoke.conftest import query_count


class TestNhlComSmoke:
    # nhl_com_done runs NHL.com scrape as a session fixture; the counts it
    # writes are what we assert against here.

    def test_player_stats_row_count_gte_500(
        self, pg: Any, smoke_season: str, nhl_com_done: int
    ) -> None:
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND gp IS NOT NULL",
            smoke_season,
        )
        assert count >= 500, f"Expected ≥500 player_stats rows, got {count}"

    def test_players_table_populated(self, pg: Any, nhl_com_done: int) -> None:
        count = query_count(pg, "SELECT COUNT(*) FROM players WHERE nhl_id IS NOT NULL")
        assert count >= 500, f"players table too sparse: {count} rows"

    def test_g_column_non_null(self, pg: Any, smoke_season: str, nhl_com_done: int) -> None:
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND g IS NOT NULL",
            smoke_season,
        )
        assert count >= 500, f"Expected ≥500 rows with non-null g, got {count}"

    def test_a_column_non_null(self, pg: Any, smoke_season: str, nhl_com_done: int) -> None:
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND a IS NOT NULL",
            smoke_season,
        )
        assert count >= 500, f"Expected ≥500 rows with non-null a, got {count}"

    def test_gp_values_in_range(self, pg: Any, smoke_season: str, nhl_com_done: int) -> None:
        """GP must be 0–82 (regular season cap)."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND gp IS NOT NULL"
            " AND (gp < 0 OR gp > 82)",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have out-of-range GP"

    def test_nhl_com_return_count_matches_sql(
        self, pg: Any, smoke_season: str, nhl_com_done: int
    ) -> None:
        """Scraper return value should match player_stats row count."""
        sql_count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND gp IS NOT NULL",
            smoke_season,
        )
        # Allow delta up to 25: players with gp=0 are upserted but excluded by IS NOT NULL
        assert abs(nhl_com_done - sql_count) <= 25, (
            f"Scraper returned {nhl_com_done} but SQL finds {sql_count} rows with gp IS NOT NULL"
        )
