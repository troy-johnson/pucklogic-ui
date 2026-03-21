"""
Natural Stat Trick (NST) stats scraper.

Fetches skater advanced stats from naturalstattrick.com and upserts them
into the ``player_stats`` Supabase table.  This scraper writes **actual**
(not projected) stats, so it subclasses ``BaseScraper`` directly — the same
pattern as ``NhlComScraper`` and ``MoneyPuckScraper``.

Target URLs (example — 2024-25 regular season, all skaters):
  sit=all  (all situations):
    https://www.naturalstattrick.com/playerteams.php
      ?fromseason=20242025&thruseason=20242025
      &stype=2&sit=all&score=all&stdoi=std&rate=n
      &team=ALL&pos=S&loc=B&toi=0&gpfilt=none
      &fd=&td=&tgfrom=0&tgthru=0&lines=single&draftteam=ALL

  Additional fetches per scrape() call:
    sit=5v5  → xgf_pct_5v5
    sit=ev   → toi_ev (EV TOI per game)
    sit=pp   → toi_pp (PP TOI per game)
    sit=sh   → toi_sh (SH TOI per game)

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
  sit=all:
    GP       → gp           (integer)
    TOI      → toi_per_game (float, total TOI / GP)
    CF%      → cf_pct
    xGF%     → xgf_pct
    SH%      → sh_pct
    PDO      → pdo
    iCF/60   → icf_per60
    ixG/60   → ixg_per60
    SCF%     → scf_pct
    iSCF/60  → scf_per60
    P1/60    → p1_per60
  sit=5v5:
    xGF%     → xgf_pct_5v5
  sit=ev:
    TOI      → toi_ev  (EV TOI per game)
  sit=pp:
    TOI      → toi_pp  (PP TOI per game)
  sit=sh:
    TOI      → toi_sh  (SH TOI per game)

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
    "&stype=2&sit={sit}&score=all&stdoi=std&rate=n"
    "&team=ALL&pos=S&loc=B&toi=0&gpfilt=none"
    "&fd=&td=&tgfrom=0&tgthru=0&lines=single&draftteam=ALL"
)

# Maps NST column headers → player_stats column names for the all-situations fetch.
# GP and TOI are handled separately in _parse_html.
_FLOAT_COL_MAP_ALL: dict[str, str] = {
    "CF%": "cf_pct",
    "xGF%": "xgf_pct",
    "SH%": "sh_pct",
    "PDO": "pdo",
    "iCF/60": "icf_per60",
    "ixG/60": "ixg_per60",
    "SCF%": "scf_pct",
    "iSCF/60": "scf_per60",
    "P1/60": "p1_per60",
}

# Situation fetches beyond all-situations: (sit param, float_col_map, toi_col_name)
_SITUATION_FETCHES: list[tuple[str, dict[str, str], str]] = [
    ("5v5", {"xGF%": "xgf_pct_5v5"}, ""),
    ("ev", {}, "toi_ev"),
    ("pp", {}, "toi_pp"),
    ("sh", {}, "toi_sh"),
]

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
    def _build_url(season: str, sit: str = "all") -> str:
        sid = NstScraper._season_id(season)
        return _NST_URL_TEMPLATE.format(sid=sid, sit=sit)

    @staticmethod
    def _parse_html(
        html: str,
        float_col_map: dict[str, str] | None = None,
        toi_col_name: str = "toi_per_game",
    ) -> list[dict[str, Any]]:
        """Parse the NST skaters table and return a list of row dicts.

        Args:
            html:          Raw HTML from the NST playerteams page.
            float_col_map: Maps NST header names → player_stats column names.
                           Defaults to ``_FLOAT_COL_MAP_ALL`` (all-situations).
                           Pass a custom map for situation-specific pages
                           (e.g. ``{"xGF%": "xgf_pct_5v5"}`` for sit=5v5).
            toi_col_name:  Column name to store the computed TOI/GP value.
                           Use ``"toi_per_game"`` (default) for all-situations,
                           ``"toi_ev"``, ``"toi_pp"``, or ``"toi_sh"`` for
                           situation-specific fetches.  Pass ``""`` to skip TOI.

        Each returned dict contains:
          - ``player_name``: str
          - ``gp``: int (when present)
          - TOI column (when ``toi_col_name`` is non-empty and TOI is parseable)
          - Any float stats mapped via ``float_col_map``

        Rows missing a player name are silently skipped.
        Unparseable numeric cells are omitted (null → not stored).
        """
        if float_col_map is None:
            float_col_map = _FLOAT_COL_MAP_ALL
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

        # Build float stat column index map from the provided (or default) map
        float_col_idx: dict[int, str] = {}
        for hdr, stat_key in float_col_map.items():
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

            # TOI (stored as toi_col_name = total_toi / gp)
            if toi_col_name and toi_col is not None and toi_col < len(cells):
                raw = cells[toi_col].get_text(strip=True)
                if raw and raw.lower() not in _MISSING_VALUES:
                    try:
                        total_toi = float(raw)
                        if gp and gp > 0:
                            row_data[toi_col_name] = total_toi / gp
                        else:
                            # No GP available — store raw total as-is
                            row_data[toi_col_name] = total_toi
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

    @staticmethod
    def _merge_situation_rows(
        primary: list[dict[str, Any]],
        *situation_lists: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge situation-specific stat dicts into the all-situations primary list.

        Each situation list is keyed by ``player_name``.  Columns from situation
        lists are merged into the matching primary row.  Players present in a
        situation list but absent from ``primary`` are dropped (primary is the
        canonical player set).  Players absent from a situation list simply lack
        the corresponding column — no key is added.

        Args:
            primary:          Rows from the all-situations (sit=all) fetch.
            *situation_lists: Any number of rows from additional situation fetches
                              (sit=5v5, sit=ev, sit=pp, sit=sh).

        Returns:
            A copy of ``primary`` with situation columns merged in-place.
        """
        result = [dict(row) for row in primary]
        for sit_rows in situation_lists:
            sit_by_name = {r["player_name"]: r for r in sit_rows}
            for row in result:
                sit_row = sit_by_name.get(row["player_name"])
                if sit_row:
                    for key, val in sit_row.items():
                        if key != "player_name":
                            row[key] = val
        return result

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

        Makes five requests to the NST playerteams endpoint (sit=all, 5v5, ev,
        pp, sh) and merges the results by player name before upserting.

        Args:
            season: e.g. "2025-26"
            db:     Supabase Client (service role)

        Returns:
            Number of player_stats rows upserted.

        Raises:
            RobotsDisallowedError: if robots.txt disallows the target URL.
        """
        base_url = self._build_url(season, sit="all")

        if not await self._check_robots_txt(base_url):
            raise RobotsDisallowedError(f"robots.txt disallows scraping {base_url}")

        # All-situations fetch (primary)
        await asyncio.sleep(self.MIN_DELAY_SECONDS)
        try:
            response = await self._get_with_retry(base_url)
        except Exception as exc:
            logger.warning(
                "NstScraper: primary fetch failed for %s (%s) — returning 0 rows. "
                "NST may be behind a Cloudflare challenge; try with a browser session.",
                season,
                exc,
            )
            return 0
        if response.status_code == 403:
            logger.warning(
                "NstScraper: 403 from NST for %s — likely Cloudflare challenge. Returning 0 rows.",
                season,
            )
            return 0
        rows = self._parse_html(response.text)

        # Situation-specific fetches — merge into primary rows
        situation_row_lists: list[list[dict[str, Any]]] = []
        for sit, float_map, toi_name in _SITUATION_FETCHES:
            await asyncio.sleep(self.MIN_DELAY_SECONDS)
            sit_url = self._build_url(season, sit=sit)
            sit_response = await self._get_with_retry(sit_url)
            sit_rows = self._parse_html(
                sit_response.text,
                float_col_map=float_map,
                toi_col_name=toi_name,
            )
            situation_row_lists.append(sit_rows)

        rows = self._merge_situation_rows(rows, *situation_row_lists)

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
