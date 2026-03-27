"""
NHL.com scraper.

Uses the public NHL Stats REST API to fetch skater points leaders and
upserts them into the ``players`` and ``player_rankings`` Supabase tables.

Usage (CLI):
    python -m scrapers.nhl_com
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from scrapers.base import BaseScraper, RobotsDisallowedError

logger = logging.getLogger(__name__)

_NHL_STATS_URL = "https://api.nhle.com/stats/rest/en/skater/summary"


class NhlComScraper(BaseScraper):
    SOURCE_NAME = "nhl_com"
    DISPLAY_NAME = "NHL.com"
    PAGE_SIZE = 100

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _season_id(season: str) -> str:
        """Convert human season to NHL API season ID.

        "2025-26" → "20252026"
        """
        start, end_short = season.split("-")
        century = start[:2]
        return f"{start}{century}{end_short}"

    def _build_url(self, season: str, start: int = 0) -> str:
        sort = json.dumps([{"property": "points", "direction": "DESC"}])
        expr = f"seasonId={self._season_id(season)} and gameTypeId=2"
        return (
            f"{_NHL_STATS_URL}"
            f"?isAggregate=false&isGame=false"
            f"&sort={sort}"
            f"&start={start}&limit={self.PAGE_SIZE}"
            f"&cayenneExp={expr}"
        )

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _upsert_source(self, db: Any) -> str:
        result = (
            db.table("sources")
            .upsert(
                {
                    "name": self.SOURCE_NAME,
                    "display_name": self.DISPLAY_NAME,
                    "active": True,
                },
                on_conflict="name",
            )
            .execute()
        )
        return result.data[0]["id"]

    def _upsert_player(self, db: Any, player: dict[str, Any]) -> str:
        result = (
            db.table("players")
            .upsert(
                {
                    "nhl_id": str(player["playerId"]),
                    "name": player.get("skaterFullName", ""),
                    "team": player.get("teamAbbrevs", ""),
                    "position": player.get("positionCode", ""),
                },
                on_conflict="nhl_id",
            )
            .execute()
        )
        return result.data[0]["id"]

    def _upsert_player_stats(
        self, db: Any, player_id: str, season: str, player: dict[str, Any]
    ) -> None:
        # Require gamesPlayed — without it the row is not meaningful.
        if player.get("gamesPlayed") is None:
            return
        int_fields = {
            "gamesPlayed": "gp",
            "goals": "g",
            "assists": "a",
            "points": "pts",
            "ppPoints": "ppp",
            "shPoints": "sh_points",
            "shots": "sog",
        }
        float_fields = {
            "faceoffWinPct": "fo_pct",
        }
        stats: dict[str, Any] = {}
        for api_key, col in int_fields.items():
            if (val := player.get(api_key)) is not None:
                stats[col] = int(val)
        for api_key, col in float_fields.items():
            if (val := player.get(api_key)) is not None:
                try:
                    stats[col] = float(val)
                except (ValueError, TypeError):
                    pass
        db.table("player_stats").upsert(
            {"player_id": player_id, "season": season, **stats},
            on_conflict="player_id,season",
        ).execute()

    def _upsert_ranking(
        self, db: Any, player_id: str, source_id: str, rank: int, season: str
    ) -> None:
        db.table("player_rankings").upsert(
            {
                "player_id": player_id,
                "source_id": source_id,
                "rank": rank,
                "season": season,
            },
            on_conflict="player_id,source_id,season",
        ).execute()

    # ------------------------------------------------------------------
    # scrape()
    # ------------------------------------------------------------------

    async def scrape(self, season: str, db: Any) -> int:  # noqa: D102
        if not await self._check_robots_txt(_NHL_STATS_URL):
            raise RobotsDisallowedError(f"robots.txt disallows scraping {_NHL_STATS_URL}")

        source_id = self._upsert_source(db)
        rows_upserted = 0
        start = 0

        while True:
            url = self._build_url(season, start)
            response = await self._get_with_retry(url)
            players: list[dict[str, Any]] = response.json().get("data", [])

            if not players:
                break

            for offset, player in enumerate(players):
                rank = start + offset + 1
                player_id = self._upsert_player(db, player)
                self._upsert_ranking(db, player_id, source_id, rank, season)
                self._upsert_player_stats(db, player_id, season, player)
                rows_upserted += 1

            if len(players) < self.PAGE_SIZE:
                break

            start += self.PAGE_SIZE
            await asyncio.sleep(self.MIN_DELAY_SECONDS)

        logger.info("NHL.com: upserted %d rankings for %s", rows_upserted, season)
        return rows_upserted


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------


async def _main() -> None:
    from core.config import settings

    if TYPE_CHECKING:
        pass
    from supabase import create_client

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    count = await NhlComScraper().scrape(settings.current_season, db)
    print(f"Upserted {count} rows.")


if __name__ == "__main__":
    from typing import TYPE_CHECKING

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
