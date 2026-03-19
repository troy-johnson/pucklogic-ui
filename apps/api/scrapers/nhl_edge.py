"""
NHL EDGE skating stats scraper.

Fetches speed burst counts and top speed from the NHL Stats API and upserts
``speed_bursts_22`` and ``top_speed`` into ``player_stats``.

No API key required. Free public endpoint.

IMPORTANT: Verify ``sprintBurstsPerGame`` and ``topSpeed`` field names against
the live API before finalising _parse_response. Update the fixture too.
"""

from __future__ import annotations

import logging
from typing import Any

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

_BASE_URL = (
    "https://api.nhle.com/stats/rest/en/skater/skating"
    "?isAggregate=true&isGame=false"
    "&start={start}&limit=100"
    "&cayenneExp=seasonId%3D{season_id}"
)
_PAGE_SIZE = 100


class NhlEdgeScraper(BaseScraper):
    """Scrapes NHL EDGE for speed burst and top speed stats (Tier 3)."""

    @staticmethod
    def _season_id(season: str) -> str:
        """'2024-25' → '20242025'"""
        left, _ = season.split("-")
        year1 = int(left)
        year2 = year1 + 1
        return f"{year1}{year2}"

    @staticmethod
    def _parse_response(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for item in data:
            player_name = item.get("playerName", "")
            if not player_name:
                continue
            rows.append(
                {
                    "player_name": player_name,
                    "speed_bursts_22": item.get("sprintBurstsPerGame"),
                    "top_speed": item.get("topSpeed"),
                }
            )
        return rows

    def _fetch_players(self, db: Any) -> list[dict[str, Any]]:
        return db.table("players").select("id,name").execute().data or []

    def _fetch_aliases(self, db: Any) -> list[dict[str, Any]]:
        return db.table("player_aliases").select("alias_name,player_id,source").execute().data or []

    def _upsert_player_stats(
        self, db: Any, player_id: str, season: str, stats: dict[str, Any]
    ) -> None:
        db.table("player_stats").upsert(
            {"player_id": player_id, "season": season, **stats},
            on_conflict="player_id,season",
        ).execute()

    async def scrape(self, season: str, db: Any) -> int:
        season_id = self._season_id(season)
        url0 = _BASE_URL.format(start=0, season_id=season_id)

        if not await self._check_robots_txt(url0):
            raise RobotsDisallowedError("robots.txt disallows NHL EDGE scraping")

        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        start = 0
        count = 0
        while True:
            url = _BASE_URL.format(start=start, season_id=season_id)
            response = await self._get_with_retry(url)
            data = response.json().get("data", [])
            if not data:
                break

            for row in self._parse_response(data):
                player_id = matcher.resolve(row["player_name"])
                if player_id is None:
                    continue
                stats = {k: v for k, v in row.items() if k != "player_name" and v is not None}
                if stats:
                    self._upsert_player_stats(db, player_id, season, stats)
                    count += 1

            if len(data) < _PAGE_SIZE:
                break
            start += _PAGE_SIZE

        logger.info("NHL EDGE: upserted %d rows for %s", count, season)
        return count


async def _main() -> None:
    from supabase import create_client

    from core.config import settings

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    scraper = NhlEdgeScraper()
    count = await scraper.scrape(settings.current_season, db)
    print(f"NHL EDGE: {count} rows upserted for {settings.current_season}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
