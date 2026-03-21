"""
Smoke test: EliteProspectsScraper

Verifies that the Elite Prospects API scraper writes elc_flag and
contract_year_flag to player_stats.

CRITICAL: The field names in _parse_response are *approximate* — documented
in the scraper source.  If test_elc_players_exist fails with 0 ELC players,
inspect the raw API response and update _parse_response + elite_prospects_sample.json.

Skipped automatically if SMOKE_ELITE_PROSPECTS_API_KEY is not set.
Match rate threshold is 80% (EP uses first/last name matching which may miss
players with name variants or AHL callups not in the players table).

Live endpoint: https://api.eliteprospects.com/v1/player-stats
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from scrapers.elite_prospects import EliteProspectsScraper
from tests.smoke.conftest import query_count

_has_key = bool(os.environ.get("SMOKE_ELITE_PROSPECTS_API_KEY"))


@pytest.mark.skipif(not _has_key, reason="SMOKE_ELITE_PROSPECTS_API_KEY not set")
class TestEliteProspectsSmoke:
    @pytest.fixture(scope="class")
    async def ep_done(self, db: Any, smoke_season: str, nhl_com_done: int) -> int:
        """Run Elite Prospects scrape once for this test class."""
        api_key = os.environ["SMOKE_ELITE_PROSPECTS_API_KEY"]
        return await EliteProspectsScraper(api_key=api_key).scrape(smoke_season, db)

    def test_scrape_returns_gte_200(self, ep_done: int) -> None:
        assert ep_done >= 200, (
            f"Elite Prospects scrape returned only {ep_done} rows. "
            "If 0: verify API field names in _parse_response match live API response."
        )

    def test_elc_flag_no_nulls(self, pg: Any, smoke_season: str, ep_done: int) -> None:
        """elc_flag has schema default=false — should never be NULL after upsert."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND elc_flag IS NULL",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have NULL elc_flag (schema default should prevent this)"

    def test_contract_year_flag_no_nulls(self, pg: Any, smoke_season: str, ep_done: int) -> None:
        """contract_year_flag has schema default=false — should never be NULL."""
        bad = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND contract_year_flag IS NULL",
            smoke_season,
        )
        assert bad == 0, f"{bad} rows have NULL contract_year_flag"

    def test_some_elc_players_exist(self, pg: Any, smoke_season: str, ep_done: int) -> None:
        """There should be at least a handful of ELC players in any NHL season.

        If this is 0, the contract type field name is wrong in _parse_response.
        Expected field: contract.type == "ELC".
        """
        count = query_count(
            pg,
            "SELECT COUNT(*) FROM player_stats WHERE season = %s AND elc_flag = true",
            smoke_season,
        )
        assert count >= 5, (
            f"Only {count} ELC players found — expected ≥5. "
            "Check _parse_response: contract.get('type') == 'ELC'"
        )

    def test_match_rate_gte_80pct(self, pg: Any, smoke_season: str, ep_done: int) -> None:
        total = query_count(pg, "SELECT COUNT(*) FROM player_stats WHERE season = %s", smoke_season)
        # EP-matched rows: player_stats rows written by EP have elc_flag set
        # (even false — any EP upsert sets both flag columns)
        ep_rows = ep_done  # return value is matched row count
        if total > 0:
            rate = ep_rows / total
            assert rate >= 0.80, f"Elite Prospects match rate {rate:.1%} < 80%"
