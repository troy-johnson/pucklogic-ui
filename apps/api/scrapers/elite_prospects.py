"""
Elite Prospects scraper.

Fetches contract type and expiry year for NHL skaters and upserts
``elc_flag`` and ``contract_year_flag`` into ``player_stats``.

Requires ELITE_PROSPECTS_API_KEY (free tier from eliteprospects.com/api).
Rate limit on free tier: ~1 req/s; MIN_DELAY_SECONDS enforces this.

IMPORTANT: The fixture + _parse_response use *approximate* field names.
Make one real API call before finalising and update _parse_response +
elite_prospects_sample.json to match the actual response shape.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.eliteprospects.com/v1"
_PAGE_SIZE = 100


class EliteProspectsScraper(BaseScraper):
    """Scrapes Elite Prospects for ELC and contract-year flags."""

    MIN_DELAY_SECONDS = 1.0

    def __init__(self, api_key: str, http: Any = None) -> None:
        super().__init__(http)
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _season_slug(season: str) -> str:
        """'2024-25' → '2024-2025'"""
        year1 = int(season.split("-")[0])
        return f"{year1}-{year1 + 1}"

    @staticmethod
    def _season_end_year(season: str) -> int:
        return int(season.split("-")[0]) + 1

    @staticmethod
    def _parse_response(data: list[dict[str, Any]], season_end_year: int) -> list[dict[str, Any]]:
        rows = []
        for item in data:
            player = item.get("player", {})
            first = player.get("firstName", "")
            last = player.get("lastName", "")
            player_name = f"{first} {last}".strip()
            if not player_name:
                continue
            contract = player.get("contract") or {}
            expiry = contract.get("expiryYear")
            rows.append(
                {
                    "player_name": player_name,
                    "elc_flag": contract.get("type") == "ELC",
                    "contract_year_flag": expiry is not None and int(expiry) == season_end_year,
                }
            )
        return rows

    # ------------------------------------------------------------------
    # DB helpers (NstScraper pattern)
    # ------------------------------------------------------------------

    def _fetch_players(self, db: Any) -> list[dict[str, Any]]:
        return db.table("players").select("id,name").execute().data or []

    def _fetch_aliases(self, db: Any) -> list[dict[str, Any]]:
        return db.table("player_aliases").select("alias_name,player_id,source").execute().data or []

    def _upsert_player_stats(
        self, db: Any, player_id: str, season: str, elc_flag: bool, contract_year_flag: bool
    ) -> None:
        db.table("player_stats").upsert(
            {
                "player_id": player_id,
                "season": season,
                "elc_flag": elc_flag,
                "contract_year_flag": contract_year_flag,
            },
            on_conflict="player_id,season",
        ).execute()

    # ------------------------------------------------------------------
    # Scrape interface
    # ------------------------------------------------------------------

    async def scrape(self, season: str, db: Any) -> int:
        """Fetch contract data from the Elite Prospects API and upsert flag columns.

        Paginates using offset/limit until all players for the season are consumed.
        Returns the number of player_stats rows upserted. Raises ValueError if
        ELITE_PROSPECTS_API_KEY is not configured.
        """
        if not self._api_key:
            raise ValueError("ELITE_PROSPECTS_API_KEY is not set")

        slug = self._season_slug(season)
        end_year = self._season_end_year(season)
        # Pass the base API URL (no key) to avoid leaking the API key into logs.
        if not await self._check_robots_txt(_BASE_URL):
            raise RobotsDisallowedError("robots.txt disallows Elite Prospects scraping")

        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        offset = 0
        total: int | None = None
        count = 0

        while True:
            url = (
                f"{_BASE_URL}/player-stats"
                f"?league.slug=nhl"
                f"&season.slug={slug}"
                f"&limit={_PAGE_SIZE}"
                f"&offset={offset}"
                f"&apiKey={self._api_key}"
            )
            response = await self._get_with_retry(url)
            payload = response.json()

            if total is None:
                total = payload.get("total", 0)

            raw_data = payload.get("data", [])
            rows = self._parse_response(raw_data, end_year)
            for row in rows:
                player_id = matcher.resolve(row["player_name"])
                if player_id is None:
                    logger.debug("Elite Prospects: unmatched %r", row["player_name"])
                    continue
                self._upsert_player_stats(
                    db, player_id, season, row["elc_flag"], row["contract_year_flag"]
                )
                count += 1

            # Advance by raw page size, not filtered row count, to avoid offset drift
            # when nameless items are skipped by _parse_response.
            offset += len(raw_data)
            if not raw_data or (total is not None and offset >= total):
                break
            await asyncio.sleep(self.MIN_DELAY_SECONDS)

        logger.info("Elite Prospects: upserted %d rows for %s", count, season)
        return count


async def _main() -> None:
    from supabase import create_client

    from core.config import settings

    if not settings.elite_prospects_api_key:
        print("ELITE_PROSPECTS_API_KEY not set — skipping")
        return
    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    scraper = EliteProspectsScraper(api_key=settings.elite_prospects_api_key)
    count = await scraper.scrape(settings.current_season, db)
    print(f"Elite Prospects: {count} rows upserted for {settings.current_season}")


if __name__ == "__main__":
    asyncio.run(_main())
