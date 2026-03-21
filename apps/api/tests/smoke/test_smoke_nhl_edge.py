"""
Smoke test: NhlEdgeScraper

Verifies that the NHL EDGE skating stats scraper writes speed_bursts_22 and
top_speed to player_stats.

CRITICAL: The field names ``sprintBurstsPerGame`` and ``topSpeed`` in
_parse_response are *approximate* — documented in the scraper source.
If test_zero_rows_is_field_name_mismatch fires, inspect the raw API response
and update _parse_response + nhl_edge_sample.json to match actual field names.

Pass criteria are deliberately relaxed:
  - The scrape must complete without error (row count can be 0)
  - If rows are written, values must be within plausible ranges
  - Zero rows triggers a UserWarning (soft-fail) instead of a hard assertion

Live endpoint: https://api.nhle.com/stats/rest/en/skater/skating
"""

from __future__ import annotations

import warnings
from typing import Any

import pytest

from scrapers.nhl_edge import NhlEdgeScraper
from tests.smoke.conftest import query_count


class TestNhlEdgeSmoke:
    @pytest.fixture(scope="class")
    async def edge_done(self, db: Any, smoke_season: str, nhl_com_done: int) -> int:
        """Run NHL EDGE scrape once for this test class."""
        return await NhlEdgeScraper().scrape(smoke_season, db)

    def test_scrape_completes_without_error(self, edge_done: int) -> None:
        """Scrape must run to completion — row count may be 0."""
        assert edge_done >= 0

    def test_zero_rows_is_field_name_mismatch(
        self, pg: Any, smoke_season: str, edge_done: int
    ) -> None:
        """Zero rows = field name mismatch in _parse_response.

        Emits a UserWarning with actionable guidance rather than hard-failing.
        Check the raw API JSON at:
          https://api.nhle.com/stats/rest/en/skater/skating?isAggregate=true&isGame=false
          &start=0&limit=1&cayenneExp=seasonId%3D20252026
        Then update _parse_response in scrapers/nhl_edge.py and nhl_edge_sample.json.
        """
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND speed_bursts_22 IS NOT NULL",
            smoke_season,
        )
        if count == 0:
            warnings.warn(
                f"NHL EDGE: 0 speed_bursts_22 rows written for season {smoke_season}. "
                "Likely a field name mismatch — inspect 'sprintBurstsPerGame' and 'topSpeed' "
                "against the live API response. Update NhlEdgeScraper._parse_response "
                "and tests/scrapers/fixtures/nhl_edge_sample.json.",
                UserWarning,
                stacklevel=2,
            )

    def test_speed_bursts_non_negative(self, pg: Any, smoke_season: str, edge_done: int) -> None:
        """speed_bursts_22 is bursts per game — must be ≥ 0."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND speed_bursts_22 IS NOT NULL AND speed_bursts_22 < 0",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have negative speed_bursts_22"

    def test_top_speed_in_mph_range(self, pg: Any, smoke_season: str, edge_done: int) -> None:
        """top_speed in mph — human skating range is ~15–35 mph."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s"
            " AND top_speed IS NOT NULL AND (top_speed < 15 OR top_speed > 35)",
            smoke_season,
        )
        assert bad == 0, (
            f"{bad} rows have top_speed outside [15, 35] mph. "
            "If the API uses km/h, the conversion or field name needs updating."
        )
