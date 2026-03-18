"""
Natural Stat Trick (NST) stats scraper.

Fetches skater advanced stats from naturalstattrick.com and upserts them
into the ``player_stats`` Supabase table.  This scraper writes **actual**
(not projected) stats, so it subclasses ``BaseScraper`` directly — the same
pattern as ``NhlComScraper`` and ``MoneyPuckScraper``.

Target URL (example — 2024-25 regular season, all situations, all skaters):
  https://www.naturalstattrick.com/playerteams.php
    ?fromseason=20242025&thruseason=20242025
    &stype=2&sit=all&score=all&stdoi=std&rate=n
    &team=ALL&pos=S&loc=B&toi=0&gpfilt=none
    &fd=&td=&tgfrom=0&tgthru=0&lines=single&draftteam=ALL

Site notes (confirmed 2026-03-17):
  - The skater table is rendered server-side and has ``id="players"``.
  - The page *may* require JavaScript for the full interactive UI, but the
    underlying table HTML is still present in the initial response.  If the
    live page becomes fully JS-rendered in future, replace the ``_get_with_retry``
    call with a Playwright fetch and update the docstring accordingly.
  - We use a synthetic HTML fixture (``tests/scrapers/fixtures/nst_skaters.html``)
    for unit tests so no real network call is required.
  - NST's robots.txt was unreachable at the time of implementation; the base
    class ``_check_robots_txt`` fails-open (assumes allowed) in that case.

Column mapping (NST header → player_stats column):
  GP    → gp          (integer)
  TOI   → toi_per_game (float, computed as total TOI / GP minutes-per-game)
  CF%   → cf_pct      (float)
  xGF%  → xgf_pct     (float)
  SH%   → sh_pct      (float)
  PDO   → pdo         (float)

Usage (CLI):
    python -m scrapers.nst
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

_NST_URL_TEMPLATE = (
    "https://www.naturalstattrick.com/playerteams.php"
    "?fromseason={sid}&thruseason={sid}"
    "&stype=2&sit=all&score=all&stdoi=std&rate=n"
    "&team=ALL&pos=S&loc=B&toi=0&gpfilt=none"
    "&fd=&td=&tgfrom=0&tgthru=0&lines=single&draftteam=ALL"
)

# Maps NST column headers → player_stats column names.
# Only float stats are listed here; GP and TOI are handled separately.
_FLOAT_COL_MAP: dict[str, str] = {
    "CF%": "cf_pct",
    "xGF%": "xgf_pct",
    "SH%": "sh_pct",
    "PDO": "pdo",
}

_MISSING_VALUES: frozenset[str] = frozenset({"", "-", "n/a", "na", "—"})


class NstScraper(BaseScraper):
    """Scrapes advanced skater stats from naturalstattrick.com into player_stats."""

    SOURCE_NAME = "nst"
    DISPLAY_NAME = "Natural Stat Trick"

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _season_id(season: str) -> str:
        """Convert human season string to NST URL season ID.

        "2024-25" → "20242025"
        "2025-26" → "20252026"
        """
        start, end_short = season.split("-")
        century = start[:2]
        return f"{start}{century}{end_short}"

    @staticmethod
    def _build_url(season: str) -> str:
        sid = NstScraper._season_id(season)
        return _NST_URL_TEMPLATE.format(sid=sid)

    @staticmethod
    def _parse_html(html: str) -> list[dict[str, Any]]:
        """Parse the NST skaters table and return a list of row dicts.

        Each dict contains:
          - ``player_name``: str — raw player name as it appears on NST
          - ``gp``: int — games played
          - ``toi_per_game``: float — average TOI per game (minutes)
          - Any float stat keys present in ``_FLOAT_COL_MAP``
            (cf_pct, xgf_pct, sh_pct, pdo)

        Rows missing a player name or GP are silently skipped.
        Unparseable numeric cells are omitted from the row (null → not stored).
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="players")
        if table is None:
            logger.warning("NstScraper: skaters table (id='players') not found in HTML")
            return []

        all_rows = table.find_all("tr")
        if not all_rows:
            return []

        # Resolve column indices from header row
        header_row = all_rows[0]
        header_cells = header_row.find_all(["th", "td"])
        headers = [th.get_text(strip=True) for th in header_cells]

        # Locate mandatory columns
        try:
            player_col = headers.index("Player")
        except ValueError:
            logger.warning("NstScraper: 'Player' column not found; headers=%s", headers)
            return []

        gp_col: int | None = headers.index("GP") if "GP" in headers else None
        toi_col: int | None = headers.index("TOI") if "TOI" in headers else None

        # Build float stat column index map
        float_col_idx: dict[int, str] = {}
        for hdr, stat_key in _FLOAT_COL_MAP.items():
            if hdr in headers:
                float_col_idx[headers.index(hdr)] = stat_key

        results: list[dict[str, Any]] = []

        for row in all_rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells or len(cells) <= player_col:
                continue

            player_name = cells[player_col].get_text(strip=True)
            if not player_name:
                continue

            row_data: dict[str, Any] = {"player_name": player_name}

            # GP (integer)
            gp: int | None = None
            if gp_col is not None and gp_col < len(cells):
                raw = cells[gp_col].get_text(strip=True)
                if raw and raw.lower() not in _MISSING_VALUES:
                    try:
                        gp = int(float(raw))
                        row_data["gp"] = gp
                    except (ValueError, TypeError):
                        pass

            # TOI (stored as toi_per_game = total_toi / gp)
            if toi_col is not None and toi_col < len(cells):
                raw = cells[toi_col].get_text(strip=True)
                if raw and raw.lower() not in _MISSING_VALUES:
                    try:
                        total_toi = float(raw)
                        if gp and gp > 0:
                            row_data["toi_per_game"] = total_toi / gp
                        else:
                            # No GP available — store raw total as-is
                            row_data["toi_per_game"] = total_toi
                    except (ValueError, TypeError):
                        pass

            # Float stats (cf_pct, xgf_pct, sh_pct, pdo)
            for col_idx, stat_key in float_col_idx.items():
                if col_idx >= len(cells):
                    continue
                raw = cells[col_idx].get_text(strip=True)
                if not raw or raw.lower() in _MISSING_VALUES:
                    continue
                try:
                    row_data[stat_key] = float(raw)
                except (ValueError, TypeError):
                    pass

            results.append(row_data)

        return results

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _fetch_players(self, db: Any) -> list[dict[str, Any]]:
        result = db.table("players").select("id,name").execute()
        return result.data or []

    def _fetch_aliases(self, db: Any) -> list[dict[str, Any]]:
        result = db.table("player_aliases").select("alias_name,player_id,source").execute()
        return result.data or []

    def _upsert_player_stats(
        self,
        db: Any,
        player_id: str,
        season: str,
        stats: dict[str, Any],
    ) -> None:
        payload = {
            "player_id": player_id,
            "season": season,
            **stats,
        }
        db.table("player_stats").upsert(
            payload,
            on_conflict="player_id,season",
        ).execute()

    # ------------------------------------------------------------------
    # scrape()
    # ------------------------------------------------------------------

    async def scrape(self, season: str, db: Any) -> int:  # noqa: D102
        """Fetch NST skater stats and upsert to player_stats.

        Args:
            season: e.g. "2025-26"
            db:     Supabase Client (service role)

        Returns:
            Number of player_stats rows upserted.

        Raises:
            RobotsDisallowedError: if robots.txt disallows the target URL.
        """
        url = self._build_url(season)

        if not await self._check_robots_txt(url):
            raise RobotsDisallowedError(f"robots.txt disallows scraping {url}")

        await asyncio.sleep(self.MIN_DELAY_SECONDS)

        response = await self._get_with_retry(url)
        rows = self._parse_html(response.text)

        if not rows:
            logger.warning("NstScraper: no rows parsed for season %s", season)
            return 0

        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        upserted = 0
        for row in rows:
            player_name = row.pop("player_name")
            player_id = matcher.resolve(player_name)
            if player_id is None:
                logger.debug(
                    "NstScraper: unmatched player %r for season %s — skipping",
                    player_name,
                    season,
                )
                continue

            stats = {k: v for k, v in row.items() if v is not None}
            if not stats:
                continue

            self._upsert_player_stats(db, player_id, season, stats)
            upserted += 1

        logger.info(
            "NstScraper: upserted %d/%d player_stats rows for season %s",
            upserted,
            len(rows),
            season,
        )
        return upserted


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------


async def _main() -> None:
    from supabase import create_client

    from core.config import settings

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    count = await NstScraper().scrape(settings.current_season, db)
    print(f"Upserted {count} rows.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
