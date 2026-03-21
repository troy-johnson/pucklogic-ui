"""
Smoke test: NstScraper

Verifies that the Natural Stat Trick scraper writes all expected Tier 1 ML
columns to player_stats.  NST makes 5 HTTP requests per scrape() call:
  - sit=all  → cf_pct, xgf_pct, sh_pct, pdo, icf_per60, ixg_per60, scf_pct,
               scf_per60, p1_per60
  - sit=5v5  → xgf_pct_5v5 (merged into the all-situations rows)
  - sit=ev   → toi_ev
  - sit=pp   → toi_pp
  - sit=sh   → toi_sh

The 4 situation fetches are independent HTTP requests.  If one fails silently,
the overall row count is still nonzero (based on sit=all).  toi_ev/pp/sh are
therefore checked with a lower 80% threshold in test_situation_columns_populated.

Uses name-based PlayerMatcher (threshold 85%).  Requires nhl_com_done to
have populated the players table first.

Live endpoint: https://www.naturalstattrick.com/playerteams.php
"""

from __future__ import annotations

from typing import Any

import pytest

from scrapers.nst import NstScraper
from tests.smoke.conftest import query_count


class TestNstSmoke:
    @pytest.fixture(scope="class")
    async def nst_done(self, db: Any, smoke_season: str, nhl_com_done: int) -> int:
        """Run NST scrape once for this test class."""
        return await NstScraper().scrape(smoke_season, db)

    @pytest.fixture(autouse=True)
    def skip_if_blocked(self, nst_done: int) -> None:
        """Skip all NST tests if the scraper returned 0 rows.

        NST is behind Cloudflare and may issue a 403 challenge to non-browser
        requests from certain IPs.  When blocked, the scraper returns 0 gracefully
        and all assertions would fail vacuously — skip instead.
        """
        if nst_done == 0:
            pytest.skip(
                "NST returned 0 rows — likely a Cloudflare 403 challenge from this IP. "
                "Verify manually: https://www.naturalstattrick.com/playerteams.php"
            )

    def test_scrape_returns_gte_500(self, nst_done: int) -> None:
        assert nst_done >= 500, f"NST scrape returned only {nst_done} rows"

    def test_cf_pct_match_rate_gte_95pct(self, pg: Any, smoke_season: str, nst_done: int) -> None:
        total = query_count(pg, "SELECT COUNT(*) FROM player_stats WHERE season = %s", smoke_season)
        matched = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND cf_pct IS NOT NULL",
            smoke_season,
        )
        if total > 0:
            rate = matched / total
            assert rate >= 0.95, f"NST cf_pct match rate {rate:.1%} < 95%"

    def test_core_columns_non_null_gte_500(self, pg: Any, smoke_season: str, nst_done: int) -> None:
        """All sit=all columns should be present for most players."""
        for col in (
            "cf_pct",
            "xgf_pct",
            "pdo",
            "icf_per60",
            "ixg_per60",
            "scf_pct",
            "scf_per60",
            "p1_per60",
        ):
            count = query_count(
                pg,
                f"SELECT COUNT(*) FROM player_stats WHERE season = %s AND {col} IS NOT NULL",  # noqa: S608
                smoke_season,
            )
            assert count >= 500, f"Expected ≥500 rows with {col}, got {count}"

    def test_situation_columns_populated(self, pg: Any, smoke_season: str, nst_done: int) -> None:
        """toi_ev/pp/sh come from 3 separate HTTP requests — use 80% threshold.

        If this test fails, check which of the 4 situation-URL fetches returned
        a page without the expected table.  The NST _parse_html logs a warning
        when the table is not found.
        """
        total = query_count(pg, "SELECT COUNT(*) FROM player_stats WHERE season = %s", smoke_season)
        if total == 0:
            pytest.skip("No player_stats rows to check")

        for col in ("toi_ev", "toi_pp", "toi_sh"):
            count = query_count(
                pg,
                f"SELECT COUNT(*) FROM player_stats WHERE season = %s AND {col} IS NOT NULL",  # noqa: S608
                smoke_season,
            )
            rate = count / total
            sit_map = {"toi_ev": "ev", "toi_pp": "pp", "toi_sh": "sh"}
            assert rate >= 0.80, (
                f"NST {col} fill rate {rate:.1%} < 80% — "
                f"check the situation-specific HTTP fetch for sit={sit_map[col]}"
            )

    def test_cf_pct_in_range(self, pg: Any, smoke_season: str, nst_done: int) -> None:
        """CF% must be between 0 and 100."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND cf_pct IS NOT NULL AND (cf_pct < 0 OR cf_pct > 100)",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have out-of-range cf_pct"

    def test_pdo_in_plausible_range(self, pg: Any, smoke_season: str, nst_done: int) -> None:
        """PDO is typically 85–115; anything outside this range signals a parsing error."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND pdo IS NOT NULL AND (pdo < 85 OR pdo > 115)",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have implausible pdo (expected 85–115)"

    def test_toi_ev_positive(self, pg: Any, smoke_season: str, nst_done: int) -> None:
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND toi_ev IS NOT NULL AND toi_ev <= 0",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have non-positive toi_ev"
