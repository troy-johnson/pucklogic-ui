"""
Smoke test: HockeyReferenceScraper

Verifies that Hockey Reference scraper writes sh_pct_career_avg and
nhl_experience to player_stats.

IMPORTANT: scrape() calls _fetch_prior_career() to merge career totals from
prior seasons in the DB.  In a freshly reset local DB there is no prior data,
so sh_pct_career_avg reflects the current season only (still a valid 0.0–1.0
fraction).  For a true multi-season career average, run scrape_history() for
a 2+ season window first — see test_scrape_history_career_avg for an optional
(but much slower) verification of that path.

robots.txt enforces Crawl-delay: 3.  This test takes ~10–30s.

Live endpoint: https://www.hockey-reference.com/leagues/NHL_{year}_skaters.html
"""

from __future__ import annotations

from typing import Any

import pytest

from scrapers.hockey_reference import HockeyReferenceScraper
from tests.smoke.conftest import query_count


class TestHockeyReferenceSmoke:
    @pytest.fixture(scope="class")
    async def hr_done(self, db: Any, smoke_season: str, nhl_com_done: int) -> int:
        """Run Hockey Reference incremental scrape once for this test class."""
        return await HockeyReferenceScraper().scrape(smoke_season, db)

    def test_scrape_returns_gte_500(self, hr_done: int) -> None:
        assert hr_done >= 500, f"Hockey Reference scrape returned only {hr_done} rows"

    def test_sh_pct_career_avg_non_null_gte_500(
        self, pg: Any, smoke_season: str, hr_done: int
    ) -> None:
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND sh_pct_career_avg IS NOT NULL",
            smoke_season,
        )
        assert count >= 500, f"Expected ≥500 sh_pct_career_avg rows, got {count}"

    def test_nhl_experience_non_null_gte_500(
        self, pg: Any, smoke_season: str, hr_done: int
    ) -> None:
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND nhl_experience IS NOT NULL",
            smoke_season,
        )
        assert count >= 500, f"Expected ≥500 nhl_experience rows, got {count}"

    def test_sh_pct_stored_as_fraction(self, pg: Any, smoke_season: str, hr_done: int) -> None:
        """sh_pct_career_avg is goals/shots — must be 0.0–1.0, NOT 0–100.

        Values > 1.0 indicate the column was accidentally stored as a percentage.
        """
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND sh_pct_career_avg IS NOT NULL"
            " AND (sh_pct_career_avg < 0 OR sh_pct_career_avg > 1.0)",
            smoke_season,
        )
        assert bad == 0, (
            f"{bad} rows have sh_pct_career_avg outside [0, 1.0]. "
            "Verify the scraper stores goals/shots, not goals/shots*100."
        )

    def test_nhl_experience_gte_1(self, pg: Any, smoke_season: str, hr_done: int) -> None:
        """Every player who appears on a season page played at least 1 NHL season."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND nhl_experience IS NOT NULL AND nhl_experience < 1",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have nhl_experience < 1"

    def test_match_rate_gte_95pct(self, pg: Any, smoke_season: str, hr_done: int) -> None:
        total = query_count(pg, "SELECT COUNT(*) FROM player_stats WHERE season = %s", smoke_season)
        matched = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND sh_pct_career_avg IS NOT NULL",
            smoke_season,
        )
        if total > 0:
            rate = matched / total
            assert rate >= 0.95, f"Hockey Reference match rate {rate:.1%} < 95%"


@pytest.mark.slow
class TestHockeyReferenceCareerAvgHistory:
    """Optional: verify sh_pct_career_avg multi-season career computation.

    Marked slow — skipped by default.  Run explicitly with:
        pytest tests/smoke/test_smoke_hockey_reference.py -m slow

    Scrapes 2024-25 only (1-season history) to validate the career-avg code
    path without the full 20-season backfill cost.
    """

    async def test_scrape_history_two_seasons(self, db: Any, pg: Any) -> None:
        scraper = HockeyReferenceScraper()
        count = await scraper.scrape_history("2024-25", "2024-25", db)
        assert count >= 500, f"scrape_history returned only {count} rows"
        # For 1-season history, sh_pct_career_avg == current-season SH%
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = '2024-25'"
            " AND sh_pct_career_avg IS NOT NULL"
            " AND (sh_pct_career_avg < 0 OR sh_pct_career_avg > 1.0)",
        )
        assert bad == 0, f"{bad} rows with out-of-range sh_pct_career_avg from scrape_history"
