"""
Smoke test: MoneyPuckScraper

Verifies that the MoneyPuck CSV scraper writes ixg_per60, g_minus_ixg, and
xgf_pct_5v5 to player_stats.

IMPORTANT: scrape() returns len(players) — the number of *ranking rows*
processed, not the number of player_stats rows written.  xgf_pct_5v5 is
only written when a 5v5 row exists for a given NHL ID.  The SQL assertions
below are the ground truth, not the return count.

Live endpoint: https://moneypuck.com/moneypuck/playerData/seasonSummary/{year}/regular/skaters.csv
"""

from __future__ import annotations

from typing import Any

import pytest

from scrapers.moneypuck import MoneyPuckScraper
from tests.smoke.conftest import query_count


class TestMoneyPuckSmoke:
    @pytest.fixture(scope="class")
    async def mp_done(self, db: Any, smoke_season: str, nhl_com_done: int) -> int:
        """Run MoneyPuck scrape once for this test class."""
        return await MoneyPuckScraper().scrape(smoke_season, db)

    def test_scrape_returns_gte_500(self, mp_done: int) -> None:
        assert mp_done >= 500, f"MoneyPuck scrape returned only {mp_done} ranking rows"

    def test_ixg_per60_non_null_gte_500(self, pg: Any, smoke_season: str, mp_done: int) -> None:
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND ixg_per60 IS NOT NULL",
            smoke_season,
        )
        assert count >= 500, f"Expected ≥500 ixg_per60 rows, got {count}"

    def test_g_minus_ixg_non_null_gte_500(self, pg: Any, smoke_season: str, mp_done: int) -> None:
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND g_minus_ixg IS NOT NULL",
            smoke_season,
        )
        assert count >= 500, f"Expected ≥500 g_minus_ixg rows, got {count}"

    def test_xgf_pct_5v5_written(self, pg: Any, smoke_season: str, mp_done: int) -> None:
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND xgf_pct_5v5 IS NOT NULL",
            smoke_season,
        )
        assert count >= 400, f"Expected ≥400 xgf_pct_5v5 rows (5v5-only column), got {count}"

    def test_xgf_pct_5v5_in_range(self, pg: Any, smoke_season: str, mp_done: int) -> None:
        """xGF% 5v5 is a percentage — must be between 0 and 100."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND xgf_pct_5v5 IS NOT NULL AND (xgf_pct_5v5 < 0 OR xgf_pct_5v5 > 100)",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have out-of-range xgf_pct_5v5"

    def test_ixg_per60_non_negative(self, pg: Any, smoke_season: str, mp_done: int) -> None:
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND ixg_per60 IS NOT NULL AND ixg_per60 < 0",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have negative ixg_per60"

    def test_match_rate_gte_95pct(self, pg: Any, smoke_season: str, mp_done: int) -> None:
        """MoneyPuck uses nhl_id for matching — expect near-perfect match rate."""
        total = query_count(pg, "SELECT COUNT(*) FROM player_stats WHERE season = %s", smoke_season)
        matched = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND ixg_per60 IS NOT NULL",
            smoke_season,
        )
        if total > 0:
            rate = matched / total
            assert rate >= 0.95, f"MoneyPuck match rate {rate:.1%} < 95%"
