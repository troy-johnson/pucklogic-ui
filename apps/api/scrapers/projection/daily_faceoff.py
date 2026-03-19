# apps/api/scrapers/projection/daily_faceoff.py
"""
DailyFaceoff projection parser (paste/upload mode).

DailyFaceoff (dailyfaceoff.com) does not publish pre-season fantasy projections
in a scrapeable tabular format.  The site is protected by Cloudflare Bot Management
which blocks all automated HTTP clients — attempts to fetch robots.txt or any
page return HTTP 403 / Cloudflare challenge pages with no usable data.

Users who have exported DailyFaceoff projection data can upload a CSV via the
custom-source upload UI.  No HTTP requests are made by this scraper.

Expected CSV format (header row required, column names case-sensitive):
    Player, G, A, PPP, SOG, HIT, BLK, GP, PIM

All stat columns are optional; any column not present in COLUMN_MAP is silently
ignored.  Missing / dash / N/A values are treated as "not projected" (null) and
are not upserted — they do not overwrite previously stored projections.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from scrapers.base_projection import BaseProjectionScraper
from scrapers.matching import PlayerMatcher
from scrapers.projection import (
    apply_column_map,
    fetch_players_and_aliases,
    log_unmatched,
    update_last_successful_scrape,
    upsert_projection_row,
    upsert_source,
)

logger = logging.getLogger(__name__)

# Maps CSV column header → player_projections column name.
COLUMN_MAP: dict[str, str] = {
    "G": "g",
    "A": "a",
    "PPP": "ppp",
    "SOG": "sog",
    "HIT": "hits",
    "BLK": "blocks",
    "GP": "gp",
    "PIM": "pim",
}

# Columns that route to player_stats instead of player_projections.
STATS_COLUMN_MAP: dict[str, str] = {
    "PP_Unit": "pp_unit",
}

PLAYER_NAME_COLUMN = "Player"


class DailyFaceoffScraper(BaseProjectionScraper):
    """Parses user-supplied DailyFaceoff projection CSVs.

    This scraper is paste/upload only — no HTTP requests.

    Usage:
        scraper = DailyFaceoffScraper()
        rows_upserted = scraper.ingest(csv_text, "2025-26", db)
    """

    SOURCE_NAME = "daily_faceoff"
    DISPLAY_NAME = "DailyFaceoff"

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_csv(text: str) -> list[dict[str, Any]]:
        """Parse a DailyFaceoff projection CSV and return a list of row dicts.

        Each dict contains:
          - ``player_name``: str  (raw name from the Player column)
          - stat keys from COLUMN_MAP with non-null integer values

        Rows with an empty Player field are skipped.
        Stat values that are empty, "-", "n/a", or "na" are omitted (not projected).
        """
        reader = csv.DictReader(io.StringIO(text.strip()))
        rows: list[dict[str, Any]] = []
        for raw_row in reader:
            player_name = raw_row.get(PLAYER_NAME_COLUMN, "").strip()
            if not player_name:
                continue
            stats = apply_column_map(raw_row, COLUMN_MAP)
            player_stats = apply_column_map(raw_row, STATS_COLUMN_MAP)
            rows.append({"player_name": player_name, **stats, **player_stats})
        return rows

    # ------------------------------------------------------------------
    # ingest() — public entry point for paste/upload pipeline
    # ------------------------------------------------------------------

    def ingest(self, csv_text: str, season: str, db: Any) -> int:
        """Parse ``csv_text``, resolve player names, and upsert to player_projections.

        Args:
            csv_text: Raw CSV string from user paste or file upload.
            season:   e.g. "2025-26"
            db:       Supabase Client (service role)

        Returns:
            Number of player_projections rows successfully upserted.
        """
        source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)
        players, aliases = fetch_players_and_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        projection_rows = self._parse_csv(csv_text)
        upserted = 0

        for row in projection_rows:
            player_name = row.pop("player_name")
            # Split player_stats columns out before writing projections
            stats_payload = {
                col: row.pop(col) for col in list(STATS_COLUMN_MAP.values()) if col in row
            }
            player_id = matcher.resolve(player_name)
            if player_id is None:
                log_unmatched(db, self.SOURCE_NAME, player_name, season)
                logger.debug("DailyFaceoff: unmatched player %r — skipping", player_name)
                continue
            upsert_projection_row(db, player_id, source_id, season, row)
            if stats_payload:
                db.table("player_stats").upsert(
                    {"player_id": player_id, "season": season, **stats_payload},
                    on_conflict="player_id,season",
                ).execute()
            upserted += 1

        if upserted > 0:
            update_last_successful_scrape(db, source_id)

        logger.info(
            "DailyFaceoff: upserted %d/%d projection rows for season %s",
            upserted,
            len(projection_rows),
            season,
        )
        return upserted

    # ------------------------------------------------------------------
    # scrape() — not supported
    # ------------------------------------------------------------------

    async def scrape(self, season: str, db: Any) -> int:
        """Not implemented — DailyFaceoff cannot be auto-scraped.

        Raises:
            NotImplementedError: always.  Use ingest(csv_text, season, db) instead.
        """
        raise NotImplementedError(
            "DailyFaceoff does not publish scrapeable projections. "
            "Use ingest(csv_text, season, db) with a user-supplied CSV."
        )
