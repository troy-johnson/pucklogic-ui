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

from scrapers.base import BaseScraper, RobotsDisallowedError

logger = logging.getLogger(__name__)

_MP_CSV_TEMPLATE = (
    "https://moneypuck.com/moneypuck/playerData/seasonSummary/{year}/regular/skaters.csv"
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
    def _parse_stats_csv(text: str) -> list[dict[str, Any]]:
        """Parse skaters CSV into player_stats rows.

        Computes derived Phase 3 Tier 1 features from the CSV columns:
          - ixg_per60   : I_F_xGoals / iceTime * 3600  (all situations)
          - g_minus_ixg : I_F_goals  - I_F_xGoals      (all situations)
          - xgf_pct_5v5 : OnIce_F_xGoals / (OnIce_F_xGoals + OnIce_A_xGoals) * 100
                          (5v5 situation only; omitted if no 5v5 row or both are zero)

        Returns one dict per player keyed by ``player_id``.
        Only ``situation == "all"`` rows are used for ixg_per60 / g_minus_ixg.
        Only ``situation == "5v5"`` rows are used for xgf_pct_5v5.
        """
        reader = csv.DictReader(io.StringIO(text))
        all_rows: dict[str, dict[str, Any]] = {}
        five_v_five: dict[str, dict[str, float]] = {}

        for row in reader:
            pid = row.get("playerId", "")
            sit = row.get("situation", "")

            if sit == "all":
                try:
                    xgoals = float(row.get("I_F_xGoals", 0) or 0)
                    goals = float(row.get("I_F_goals", 0) or 0)
                    ice_time = float(row.get("iceTime", 0) or 0)
                except (ValueError, TypeError):
                    continue

                ixg_per60 = (xgoals / ice_time * 3600) if ice_time > 0 else 0.0
                g_minus_ixg = goals - xgoals
                all_rows[pid] = {
                    "player_id": pid,
                    "ixg_per60": ixg_per60,
                    "g_minus_ixg": g_minus_ixg,
                }

            elif sit == "5on5":
                try:
                    on_ice_f = float(row.get("OnIce_F_xGoals", 0) or 0)
                    on_ice_a = float(row.get("OnIce_A_xGoals", 0) or 0)
                except (ValueError, TypeError):
                    continue

                total = on_ice_f + on_ice_a
                if total > 0:
                    five_v_five[pid] = {"xgf_pct_5v5": on_ice_f / total * 100}

        # Merge 5v5 stats into all-situation rows
        for pid, stats in five_v_five.items():
            if pid in all_rows:
                all_rows[pid].update(stats)

        return list(all_rows.values())

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

    def _upsert_player_stats(
        self, db: Any, player_id: str, season: str, stats: dict[str, Any]
    ) -> None:
        payload = {"player_id": player_id, "season": season, **stats}
        db.table("player_stats").upsert(
            payload,
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
        csv_url = self._csv_url(season)

        if not await self._check_robots_txt(csv_url):
            raise RobotsDisallowedError(f"robots.txt disallows scraping {csv_url}")

        response = await self._get_with_retry(csv_url)
        players = self._parse_csv(response.text)
        stats_rows = self._parse_stats_csv(response.text)
        source_id = self._upsert_source(db)

        # Build a nhl_id → stats map for the player_stats write
        stats_by_nhl_id = {r["player_id"]: r for r in stats_rows}

        for rank, row in enumerate(players, start=1):
            player_id = self._upsert_player(db, row)
            self._upsert_ranking(db, player_id, source_id, rank, season)
            # Write derived Phase 3 stats if available
            nhl_id = row["player_id"]
            if nhl_id in stats_by_nhl_id:
                stats = {k: v for k, v in stats_by_nhl_id[nhl_id].items() if k != "player_id"}
                self._upsert_player_stats(db, player_id, season, stats)

        logger.info("MoneyPuck: upserted %d rankings for %s", len(players), season)
        return len(players)


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------


def _iter_seasons(start: str, end: str) -> list[str]:
    """Return season strings from start to end inclusive.

    "2008-09", "2025-26" → ["2008-09", "2009-10", ..., "2025-26"]
    """
    start_year = int(start.split("-")[0])
    end_year = int(end.split("-")[0])
    seasons = []
    for y in range(start_year, end_year + 1):
        short = str(y + 1)[-2:]
        seasons.append(f"{y}-{short}")
    return seasons


async def _main() -> None:
    import argparse

    from supabase import create_client

    from core.config import settings

    parser = argparse.ArgumentParser(description="MoneyPuck scraper")
    parser.add_argument(
        "--history",
        action="store_true",
        help=(
            "Backfill all seasons from 2005-06 to current_season. "
            "MoneyPuck data is available from 2009-10; earlier seasons return 404 "
            "and are skipped gracefully. Run before the first training run."
        ),
    )
    args = parser.parse_args()

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    scraper = MoneyPuckScraper()

    if args.history:
        seasons = _iter_seasons("2005-06", settings.current_season)
        total = 0
        for season in seasons:
            try:
                count = await scraper.scrape(season, db)
                total += count
                print(f"MoneyPuck {season}: {count} rows")
            except Exception as exc:
                logger.warning("MoneyPuck %s: skipped — %s", season, exc)
        print(f"MoneyPuck history: {total} total rows upserted")
    else:
        count = await scraper.scrape(settings.current_season, db)
        print(f"Upserted {count} rows.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
