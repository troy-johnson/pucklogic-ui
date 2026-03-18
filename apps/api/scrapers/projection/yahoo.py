# apps/api/scrapers/projection/yahoo.py
"""
Yahoo Fantasy Hockey projection scraper.

Uses the unofficial yahoo-fantasy-api Python library (OAuth2).
Requires YAHOO_OAUTH_REFRESH_TOKEN in .env / GitHub Actions secrets.

Yahoo stat IDs → our player_projections columns.
Verify stat IDs by calling the API and inspecting a live response.
Last verified: 2026-03-18
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from scrapers.base_projection import BaseProjectionScraper
from scrapers.matching import PlayerMatcher
from scrapers.projection import (
    fetch_players_and_aliases,
    log_unmatched,
    update_last_successful_scrape,
    upsert_projection_row,
    upsert_source,
)

logger = logging.getLogger(__name__)


def fetch_all_yahoo_nhl_players(oauth_token: str) -> list[dict[str, Any]]:
    """Fetch all NHL players with stats from Yahoo Fantasy API using pagination.

    Paginates via game.player_stats() with start/count instead of calling
    player_details("all") which is a name-search that returns only a handful
    of players.

    Args:
        oauth_token: YAHOO_OAUTH_REFRESH_TOKEN value from settings.

    Returns:
        List of raw Yahoo player dicts (name, eligible_positions, player_stats).
    """
    import yahoo_fantasy_api as yfa  # type: ignore[import-untyped]

    oauth = yfa.OAuth2(None, None, from_file=None)
    oauth.refresh_access_token(oauth_token)
    game = yfa.Game(oauth, "nhl")

    all_players: list[dict[str, Any]] = []
    start = 0
    count = 25
    while True:
        batch = game.player_stats([], req_type="season", start=start, count=count)
        if not batch:
            break
        all_players.extend(batch)
        if len(batch) < count:
            break
        start += count
    return all_players


# Yahoo stat_id → our stat column
# Verify these by inspecting live Yahoo API responses; they can change each season.
YAHOO_STAT_MAP: dict[str, str] = {
    "1": "gp",
    "5": "g",
    "6": "a",
    "7": "ppp",
    "14": "sog",
    "16": "pim",
    "31": "hits",
    "32": "blocks",
    # Goalie stats
    "19": "w",
    "21": "ga",
    "23": "sv",
    "24": "sv_pct",
    "25": "so",
}


def _parse_stat_value(stat_id: str, raw_value: str) -> Any:
    """Convert Yahoo stat value string to int or float."""
    if not raw_value or raw_value in {"-", ""}:
        return None
    try:
        if stat_id == "24":  # sv_pct is float
            return float(raw_value)
        return int(float(raw_value))
    except (ValueError, TypeError):
        return None


class YahooScraper(BaseProjectionScraper):
    SOURCE_NAME = "yahoo"
    DISPLAY_NAME = "Yahoo Fantasy"

    @staticmethod
    def _parse_player(player: dict[str, Any]) -> dict[str, Any]:
        """Extract player_name and mapped stats from a Yahoo player dict."""
        name = player.get("name", {}).get("full", "")
        result: dict[str, Any] = {"player_name": name}

        stats_list = player.get("player_stats", {}).get("stats", [])
        for stat in stats_list:
            stat_id = str(stat.get("stat_id", ""))
            if stat_id not in YAHOO_STAT_MAP:
                continue
            col = YAHOO_STAT_MAP[stat_id]
            val = _parse_stat_value(stat_id, str(stat.get("value", "")))
            if val is not None:
                result[col] = val

        return result

    def _fetch_yahoo_players(self) -> list[dict[str, Any]]:
        """Fetch all NHL players with projected stats from Yahoo Fantasy API."""
        from core.config import settings

        return fetch_all_yahoo_nhl_players(settings.yahoo_oauth_refresh_token)

    async def scrape(self, season: str, db: Any) -> int:
        from core.config import settings

        if not settings.yahoo_oauth_refresh_token:
            logger.warning("Yahoo: no OAuth refresh token configured — skipping")
            return 0

        source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)
        players, aliases = fetch_players_and_aliases(db)
        matcher = PlayerMatcher(players, aliases)

        try:
            yahoo_players = await asyncio.to_thread(self._fetch_yahoo_players)
        except Exception as exc:
            logger.error("Yahoo: API fetch failed: %s", exc)
            return 0

        upserted = 0
        for yahoo_player in yahoo_players:
            row = self._parse_player(yahoo_player)
            player_name = row.pop("player_name", "")
            if not player_name:
                continue
            player_id = matcher.resolve(player_name)
            if player_id is None:
                log_unmatched(db, self.SOURCE_NAME, player_name, season)
                continue
            upsert_projection_row(db, player_id, source_id, season, row)
            upserted += 1

        update_last_successful_scrape(db, source_id)
        logger.info("%s: upserted %d projection rows for %s", self.DISPLAY_NAME, upserted, season)
        return upserted


if __name__ == "__main__":
    import asyncio

    from core.dependencies import get_db
    asyncio.run(YahooScraper().scrape("2025-26", get_db()))
