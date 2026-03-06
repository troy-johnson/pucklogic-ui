"""
MoneyPuck scraper.

Downloads the MoneyPuck skaters CSV for a given season, ranks players by
individual expected goals (I_F_xGoals, "all" situations only), and upserts
the results into Supabase.

Usage (CLI):
    python -m scrapers.moneypuck
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
from typing import Any

import httpx

from scrapers.base import BaseScraper, RobotsDisallowedError

logger = logging.getLogger(__name__)

_MP_CSV_TEMPLATE = (
    "https://moneypuck.com/moneypuck/playerData/seasonSummary"
    "/{year}/regular/skaters.csv"
)


class MoneyPuckScraper(BaseScraper):
    SOURCE_NAME = "moneypuck"
    DISPLAY_NAME = "MoneyPuck"

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _season_year(season: str) -> str:
        """'2025-26' → '2025'"""
        return season.split("-")[0]

    @staticmethod
    def _csv_url(season: str) -> str:
        year = MoneyPuckScraper._season_year(season)
        return _MP_CSV_TEMPLATE.format(year=year)

    @staticmethod
    def _parse_csv(text: str) -> list[dict[str, Any]]:
        """Parse skaters CSV.

        Filters to ``situation == "all"`` rows only, then returns rows
        sorted descending by ``I_F_xGoals``.
        """
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            if row.get("situation", "") != "all":
                continue
            try:
                xgoals = float(row["I_F_xGoals"])
            except (KeyError, ValueError):
                xgoals = 0.0
            rows.append(
                {
                    "player_id": row.get("playerId", ""),
                    "name": row.get("name", ""),
                    "team": row.get("team", ""),
                    "position": row.get("position", ""),
                    "xgoals": xgoals,
                }
            )
        rows.sort(key=lambda r: r["xgoals"], reverse=True)
        return rows

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _upsert_source(self, db: Any) -> str:
        result = (
            db.table("sources")
            .upsert(
                {"name": self.SOURCE_NAME, "display_name": self.DISPLAY_NAME, "active": True},
                on_conflict="name",
            )
            .execute()
        )
        return result.data[0]["id"]

    def _upsert_player(self, db: Any, row: dict[str, Any]) -> str:
        result = (
            db.table("players")
            .upsert(
                {
                    "nhl_id": row["player_id"],
                    "name": row["name"],
                    "team": row["team"],
                    "position": row["position"],
                },
                on_conflict="nhl_id",
            )
            .execute()
        )
        return result.data[0]["id"]

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
        csv_url = self._csv_url(season)

        if not await self._check_robots_txt(csv_url):
            raise RobotsDisallowedError(
                f"robots.txt disallows scraping {csv_url}"
            )

        response = await self._get_with_retry(csv_url)
        players = self._parse_csv(response.text)
        source_id = self._upsert_source(db)

        for rank, row in enumerate(players, start=1):
            player_id = self._upsert_player(db, row)
            self._upsert_ranking(db, player_id, source_id, rank, season)

        logger.info("MoneyPuck: upserted %d rankings for %s", len(players), season)
        return len(players)


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------

async def _main() -> None:
    from core.config import settings
    from supabase import create_client

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    count = await MoneyPuckScraper().scrape(settings.current_season, db)
    print(f"Upserted {count} rows.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
