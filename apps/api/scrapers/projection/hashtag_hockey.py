# apps/api/scrapers/projection/hashtag_hockey.py
"""
HashtagHockey pre-season projection scraper.

Source URL: https://hashtaghockey.com/fantasy-hockey-projections

Site notes:
- Server-rendered ASP.NET WebForms page (static HTML — no JS rendering required).
- Table id: ContentPlaceHolder1_GridView1
- robots.txt returns 404 (no file present) — scraper will fail-open (assume allowed).
- Data is PER-GAME RATES (G/gp, A/gp, SOG/gp, HIT/gp, PPP/gp, +/-/gp).
  Scraper multiplies each rate × GP to produce projected season totals (integers).
- Goalie rows are included (SHO, W, SV%, GAA columns); skater-only columns are
  empty for goalies and are skipped (None).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bs4 import BeautifulSoup

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

PROJECTIONS_URL = "https://hashtaghockey.com/fantasy-hockey-projections"

# Maps column header text → player_projections column name.
# Data is per-game rates; _parse_html multiplies each rate by GP before storing.
# "G", "A", "+/-", "SOG", "HIT", "PPP" are per-game rates for skaters.
# "SHO", "W", "SV%", "GAA" are per-game/per-start rates for goalies.
# "GP" and "PLAYER" are handled separately (not via apply_column_map).
_RATE_COL_MAP: dict[str, str] = {
    "G": "g",
    "A": "a",
    "+/-": "plus_minus",
    "SOG": "sog",
    "HIT": "hits",
    "PPP": "ppp",
}

_GOALIE_RATE_COL_MAP: dict[str, str] = {
    "SHO": "so",
    "W": "w",
    "GAA": "ga",  # store as per-game average — caller may override
}

# SV% is stored as a float directly (not multiplied by GP)
_FLOAT_COL_MAP: dict[str, str] = {
    "SV%": "sv_pct",
}


class HashtagHockeyScraper(BaseScraper, BaseProjectionScraper):
    """Scrapes projected skater and goalie stats from hashtaghockey.com."""

    SOURCE_NAME = "hashtag_hockey"
    DISPLAY_NAME = "Hashtag Hockey"

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_html(self, html: str) -> list[dict[str, Any]]:
        """Parse the projections table and return a list of row dicts.

        Each dict contains:
          - ``player_name``: str
          - ``gp``: int
          - stat keys mapped from _RATE_COL_MAP (season totals = rate × GP)
          - goalie stat keys where applicable
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="ContentPlaceHolder1_GridView1")
        if table is None:
            logger.warning("HashtagHockey: projections table not found in HTML")
            return []

        all_rows = table.find_all("tr")
        if not all_rows:
            return []

        # Resolve header positions
        header_cells = all_rows[0].find_all("th")
        headers = [th.get_text(strip=True) for th in header_cells]
        try:
            player_col = headers.index("PLAYER")
            gp_col = headers.index("GP")
        except ValueError:
            logger.warning(
                "HashtagHockey: expected PLAYER and GP columns not found; headers=%s",
                headers,
            )
            return []

        # Build col-index maps for rate and float columns
        rate_col_idx: dict[int, str] = {}
        for hdr, stat_key in _RATE_COL_MAP.items():
            if hdr in headers:
                rate_col_idx[headers.index(hdr)] = stat_key

        goalie_rate_idx: dict[int, str] = {}
        for hdr, stat_key in _GOALIE_RATE_COL_MAP.items():
            if hdr in headers:
                goalie_rate_idx[headers.index(hdr)] = stat_key

        float_col_idx: dict[int, str] = {}
        for hdr, stat_key in _FLOAT_COL_MAP.items():
            if hdr in headers:
                float_col_idx[headers.index(hdr)] = stat_key

        results: list[dict[str, Any]] = []

        for row in all_rows[1:]:
            cells = row.find_all("td")
            if len(cells) <= max(player_col, gp_col):
                continue

            player_name = cells[player_col].get_text(strip=True)
            if not player_name:
                continue

            gp_text = cells[gp_col].get_text(strip=True)
            try:
                gp = int(float(gp_text))
            except (ValueError, TypeError):
                logger.debug("HashtagHockey: invalid GP %r for %s — skipping", gp_text, player_name)
                continue

            if gp <= 0:
                continue

            row_data: dict[str, Any] = {"player_name": player_name, "gp": gp}

            # Per-game rate → season total (integer)
            for col_idx, stat_key in rate_col_idx.items():
                if col_idx >= len(cells):
                    continue
                raw = cells[col_idx].get_text(strip=True)
                _MISSING = {"", "-", "n/a", "na", "—"}
                if not raw or raw.lower() in _MISSING:
                    continue
                try:
                    rate = float(raw)
                    row_data[stat_key] = round(rate * gp)
                except (ValueError, TypeError):
                    pass

            # Goalie per-start rate → season total (integer)
            for col_idx, stat_key in goalie_rate_idx.items():
                if col_idx >= len(cells):
                    continue
                raw = cells[col_idx].get_text(strip=True)
                if not raw or raw.strip() in {"", "-", "n/a"}:
                    continue
                try:
                    rate = float(raw)
                    row_data[stat_key] = round(rate * gp)
                except (ValueError, TypeError):
                    pass

            # Float columns (sv_pct — stored as-is, no GP multiplication)
            for col_idx, stat_key in float_col_idx.items():
                if col_idx >= len(cells):
                    continue
                raw = cells[col_idx].get_text(strip=True)
                # SV% cell may look like "0.902(24.8/27.5)" — extract leading float
                if not raw or raw.startswith("("):
                    continue
                raw_clean = raw.split("(")[0].strip()
                if not raw_clean:
                    continue
                try:
                    row_data[stat_key] = float(raw_clean)
                except (ValueError, TypeError):
                    pass

            results.append(row_data)

        return results

    # ------------------------------------------------------------------
    # scrape()
    # ------------------------------------------------------------------

    async def scrape(self, season: str, db: Any) -> int:
        """Fetch projections from HashtagHockey and upsert to player_projections.

        Args:
            season: e.g. "2025-26"
            db:     Supabase Client (service role)

        Returns:
            Number of player_projections rows upserted.

        Raises:
            RobotsDisallowedError: if robots.txt disallows the target URL.
        """
        allowed = await self._check_robots_txt(PROJECTIONS_URL)
        if not allowed:
            raise RobotsDisallowedError(f"robots.txt disallows scraping {PROJECTIONS_URL}")

        await asyncio.sleep(self.MIN_DELAY_SECONDS)

        response = await self._get_with_retry(PROJECTIONS_URL)
        html = response.text

        rows = self._parse_html(html)
        if not rows:
            logger.warning("HashtagHockey: no rows parsed from HTML")
            return 0

        source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)

        players, aliases = fetch_players_and_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        upserted = 0
        for row in rows:
            player_name = row.pop("player_name")
            player_id = matcher.resolve(player_name)
            if player_id is None:
                log_unmatched(db, self.SOURCE_NAME, player_name, season)
                logger.debug("HashtagHockey: unmatched player %r — skipping", player_name)
                continue

            # Strip None values (apply_column_map contract)
            stats = {k: v for k, v in row.items() if v is not None}
            upsert_projection_row(db, player_id, source_id, season, stats)
            upserted += 1

        if upserted > 0:
            update_last_successful_scrape(db, source_id)

        logger.info(
            "HashtagHockey: upserted %d/%d projection rows for season %s",
            upserted,
            len(rows),
            season,
        )
        return upserted
