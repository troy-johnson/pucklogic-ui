"""
Hockey Reference stats scraper.

Fetches per-season goals and shots for all skaters. Computes rolling career
SH% and NHL experience, then upserts them into ``player_stats``.

Target URL (example — 2024-25 season):
  https://www.hockey-reference.com/leagues/NHL_2025_skaters.html

robots.txt specifies Crawl-delay: 3 — MIN_DELAY_SECONDS enforces this.

Two modes:
  scrape_history(start, end, db)  — full backfill; use for initial load and
                                    the annual retraining cron.
  scrape(season, db)              — incremental; fetches current season from
                                    HR, loads prior career totals from DB,
                                    upserts the new season's values.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.hockey-reference.com/leagues/NHL_{year}_skaters.html"


class HockeyReferenceScraper(BaseScraper):
    """Scrapes Hockey Reference for career SH% and NHL experience."""

    MIN_DELAY_SECONDS = 3.0  # robots.txt Crawl-delay

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _season_to_year(season: str) -> int:
        """'2024-25' → 2025  |  '2099-00' → 2100"""
        year1 = int(season.split("-")[0])
        return year1 + 1

    @staticmethod
    def _build_url(season: str) -> str:
        return _BASE_URL.format(year=HockeyReferenceScraper._season_to_year(season))

    @staticmethod
    def _parse_html(html: str) -> list[dict[str, Any]]:
        """Parse the ``id="stats"`` skaters table.

        Returns list of dicts: player_name, gp, goals, shots, sh_pct (None if shots==0).
        Skips rows with class "thead" (mid-table repeat headers).
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "player_stats"})
        if table is None:
            logger.warning("Hockey Reference: table id='player_stats' not found")
            return []

        rows: list[dict[str, Any]] = []
        for tr in table.find("tbody").find_all("tr"):
            if "thead" in (tr.get("class") or []):
                continue
            # data-stat "name_display" (current); fall back to legacy "player"
            td = tr.find("td", {"data-stat": "name_display"}) or tr.find(
                "td", {"data-stat": "player"}
            )
            if td is None:
                continue
            player_name = td.get_text(strip=True)
            if not player_name:
                continue

            def _int(stat: str, _tr: Any = tr) -> int:
                cell = _tr.find("td", {"data-stat": stat})
                txt = cell.get_text(strip=True) if cell else ""
                return int(txt) if txt else 0

            goals = _int("goals")
            shots = _int("shots")
            # data-stat "games" (current); fall back to legacy "games_played"
            gp = _int("games") or _int("games_played")
            rows.append(
                {
                    "player_name": player_name,
                    "gp": gp,
                    "goals": goals,
                    "shots": shots,
                    "sh_pct": (goals / shots) if shots > 0 else None,
                }
            )

        return rows

    @staticmethod
    def _compute_career_stats(
        rows_by_season: dict[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Accumulate per-player career running totals across seasons.

        Returns: {player_name: {season: {sh_pct_career_avg, career_goals,
                                          career_shots, nhl_experience}}}
        Seasons processed in chronological order regardless of dict insertion order.
        """
        running: dict[str, dict[str, Any]] = {}
        result: dict[str, dict[str, dict[str, Any]]] = {}

        for season in sorted(rows_by_season):
            for row in rows_by_season[season]:
                name = row["player_name"]
                acc = running.setdefault(name, {"goals": 0, "shots": 0, "experience": 0})

                acc["goals"] += row.get("goals", 0)
                acc["shots"] += row.get("shots", 0)
                if row.get("gp", 0) > 0:
                    acc["experience"] += 1

                sh_pct_career = acc["goals"] / acc["shots"] if acc["shots"] > 0 else None
                result.setdefault(name, {})[season] = {
                    "sh_pct_career_avg": sh_pct_career,
                    "career_goals": acc["goals"],
                    "career_shots": acc["shots"],
                    "nhl_experience": acc["experience"],
                }

        return result

    # ------------------------------------------------------------------
    # DB helpers (follow NstScraper pattern exactly)
    # ------------------------------------------------------------------

    def _fetch_players(self, db: Any) -> list[dict[str, Any]]:
        return db.table("players").select("id,name").execute().data or []

    def _fetch_aliases(self, db: Any) -> list[dict[str, Any]]:
        return db.table("player_aliases").select("alias_name,player_id,source").execute().data or []

    def _fetch_prior_career(self, db: Any, season: str) -> dict[str, dict[str, Any]]:
        """Return most-recent-prior-season career totals keyed by player_id."""
        rows = (
            db.table("player_stats")
            .select("player_id,season,career_goals,career_shots,nhl_experience")
            .lt("season", season)
            .execute()
            .data
            or []
        )
        # Keep only the most recent season per player
        best: dict[str, dict[str, Any]] = {}
        for row in rows:
            pid = row["player_id"]
            if pid not in best or row["season"] > best[pid]["season"]:
                best[pid] = row
        return best

    def _upsert_player_stats(
        self,
        db: Any,
        player_id: str,
        season: str,
        sh_pct_career_avg: float | None,
        career_goals: int,
        career_shots: int,
        nhl_experience: int,
    ) -> None:
        payload: dict[str, Any] = {
            "player_id": player_id,
            "season": season,
            "career_goals": career_goals,
            "career_shots": career_shots,
            "nhl_experience": nhl_experience,
        }
        if sh_pct_career_avg is not None:
            payload["sh_pct_career_avg"] = round(sh_pct_career_avg, 4)
        db.table("player_stats").upsert(payload, on_conflict="player_id,season").execute()

    # ------------------------------------------------------------------
    # Scrape interface
    # ------------------------------------------------------------------

    async def scrape(self, season: str, db: Any) -> int:
        """Fetch one season from HR, merge with prior DB career totals, upsert.

        Best used when ``scrape_history()`` has already established career
        baselines in the DB. Without prior data, treats this as the player's
        first season (career totals = current season only).
        """
        url = self._build_url(season)
        if not await self._check_robots_txt(url):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")

        response = await self._get_with_retry(url)
        rows = self._parse_html(response.text)

        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)
        prior = self._fetch_prior_career(db, season)

        count = 0
        for row in rows:
            player_id = matcher.resolve(row["player_name"])
            if player_id is None:
                logger.debug("Hockey Reference: unmatched %r — skipping", row["player_name"])
                continue

            prev = prior.get(player_id, {})
            career_goals = prev.get("career_goals", 0) + row["goals"]
            career_shots = prev.get("career_shots", 0) + row["shots"]
            experience = prev.get("nhl_experience", 0) + (1 if row["gp"] > 0 else 0)
            sh_pct_career = career_goals / career_shots if career_shots > 0 else None

            self._upsert_player_stats(
                db, player_id, season, sh_pct_career, career_goals, career_shots, experience
            )
            count += 1

        logger.info("Hockey Reference: upserted %d rows for %s", count, season)
        return count

    async def scrape_history(self, start_season: str, end_season: str, db: Any) -> int:
        """Full backfill: fetch all seasons in [start, end], compute exact career totals.

        Fetches each season page sequentially respecting the 3s crawl delay.
        Returns total rows upserted.
        """
        # Check robots.txt once using the start-season URL. All season pages share
        # the same domain and /en/leagues/NHL_*.html path pattern, so a single
        # check is sufficient for the entire backfill run.
        if not await self._check_robots_txt(self._build_url(start_season)):
            raise RobotsDisallowedError("robots.txt disallows Hockey Reference scraping")

        start_year = self._season_to_year(start_season) - 1
        end_year = self._season_to_year(end_season) - 1
        seasons = [f"{y}-{str(y + 1)[2:]}" for y in range(start_year, end_year + 1)]

        rows_by_season: dict[str, list[dict[str, Any]]] = {}
        for i, season in enumerate(seasons):
            response = await self._get_with_retry(self._build_url(season))
            rows_by_season[season] = self._parse_html(response.text)
            logger.info("Hockey Reference: fetched %s (%d/%d)", season, i + 1, len(seasons))
            if i < len(seasons) - 1:
                await asyncio.sleep(self.MIN_DELAY_SECONDS)

        career_result = self._compute_career_stats(rows_by_season)
        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        total = 0
        for player_name, season_data in career_result.items():
            player_id = matcher.resolve(player_name)
            if player_id is None:
                continue
            for season, stats in season_data.items():
                self._upsert_player_stats(
                    db,
                    player_id,
                    season,
                    stats.get("sh_pct_career_avg"),
                    stats["career_goals"],
                    stats["career_shots"],
                    stats["nhl_experience"],
                )
                total += 1

        logger.info("Hockey Reference history: %d rows upserted", total)
        return total


async def _main() -> None:
    import argparse

    from supabase import create_client

    from core.config import settings

    parser = argparse.ArgumentParser(description="Hockey Reference scraper")
    parser.add_argument(
        "--history",
        action="store_true",
        help=(
            "Backfill all seasons from 2008-09 to current_season. "
            "Required before the first training run and in the annual retrain workflow."
        ),
    )
    args = parser.parse_args()

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    scraper = HockeyReferenceScraper()

    if args.history:
        count = await scraper.scrape_history("2008-09", settings.current_season, db)
        print(
            f"Hockey Reference history: {count} rows upserted "
            f"(2008-09 to {settings.current_season})"
        )
    else:
        count = await scraper.scrape(settings.current_season, db)
        print(f"Hockey Reference: {count} rows upserted for {settings.current_season}")


if __name__ == "__main__":
    asyncio.run(_main())
