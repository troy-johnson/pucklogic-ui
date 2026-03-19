# apps/api/scrapers/projection/fantrax.py
"""
Fantrax projection scraper.

Fantrax does not have a documented public API.
Implementation uses session-cookie-based XHR calls discovered via devtools.

If API access proves too brittle, set AUTO_SCRAPE = False to fall back to
paste/upload mode (same as Dobber — no HTTP, just CSV parse).

Requires FANTRAX_SESSION_TOKEN in .env / GitHub Actions secrets.
Last verified: <DATE> — re-verify XHR endpoints each season.
"""

from __future__ import annotations

import logging
from typing import Any

from scrapers.base import BaseScraper, RobotsDisallowedError
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

# Set to False and implement ingest() if API access is not feasible
AUTO_SCRAPE = True  # Update after investigation

# FILL IN after inspecting XHR calls in devtools
FANTRAX_API_URL = "https://www.fantrax.com/newapi/fantrax-api.go"

# Fantrax stat key → our player_projections column (FILL IN after API inspection)
FANTRAX_STAT_MAP: dict[str, str] = {
    # "GP": "gp",
    # "G": "g",
    # "A": "a",
    # Fill in from actual API response keys
}


class FantraxScraper(BaseScraper, BaseProjectionScraper):
    SOURCE_NAME = "fantrax"
    DISPLAY_NAME = "Fantrax"

    async def _fetch_fantrax_players(self) -> list[dict[str, Any]]:
        """Fetch player projection data from Fantrax API."""
        from core.config import settings

        if not settings.fantrax_session_token:
            return []

        # FILL IN with actual request params after devtools investigation
        resp = await self._get_with_retry(
            FANTRAX_API_URL,
            params={"msgs": "getPlayersTable"},  # Update params
            cookies={"fantrax.session": settings.fantrax_session_token},
        )
        data = resp.json()
        # FILL IN: navigate to the player list in the response
        return data.get("responses", [{}])[0].get("data", {}).get("rows", [])

    @staticmethod
    def _parse_player(raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw Fantrax player row to projection stats."""
        # FILL IN after inspecting actual API response shape
        name = raw.get("player", {}).get("name", "") or raw.get("name", "")
        result: dict[str, Any] = {"player_name": name}
        for fantrax_key, stat_col in FANTRAX_STAT_MAP.items():
            val = raw.get(fantrax_key)
            if val is not None:
                try:
                    result[stat_col] = int(float(val))
                except (ValueError, TypeError):
                    pass
        return result

    async def scrape(self, season: str, db: Any) -> int:
        from core.config import settings

        if not settings.fantrax_session_token:
            logger.warning("Fantrax: no session token configured — skipping")
            return 0

        if not AUTO_SCRAPE:
            logger.info("Fantrax: AUTO_SCRAPE disabled — use paste/upload mode")
            return 0

        allowed = await self._check_robots_txt(FANTRAX_API_URL)
        if not allowed:
            raise RobotsDisallowedError(f"robots.txt disallows scraping {FANTRAX_API_URL}")

        source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)
        players, aliases = fetch_players_and_aliases(db)
        matcher = PlayerMatcher(players, aliases)

        try:
            fantrax_players = await self._fetch_fantrax_players()
        except Exception as exc:
            logger.error("Fantrax: API fetch failed: %s", exc)
            return 0

        upserted = 0
        for raw in fantrax_players:
            row = self._parse_player(raw)
            player_name = row.pop("player_name", "")
            if not player_name:
                continue
            player_id = matcher.resolve(player_name)
            if player_id is None:
                log_unmatched(db, self.SOURCE_NAME, player_name, season)
                continue
            upsert_projection_row(db, player_id, source_id, season, row)
            upserted += 1

        if upserted > 0:
            update_last_successful_scrape(db, source_id)
        logger.info("%s: upserted %d rows for %s", self.DISPLAY_NAME, upserted, season)
        return upserted
