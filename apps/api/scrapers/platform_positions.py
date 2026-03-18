# apps/api/scrapers/platform_positions.py
"""
player_platform_positions ingestion.

Fetches position eligibility from ESPN, Yahoo, and Fantrax and
upserts to the player_platform_positions table.

Run pre-season (September). Safe to re-run — uses UPSERT.

Usage:
    python -m scrapers.platform_positions
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from scrapers.matching import PlayerMatcher
from scrapers.projection.yahoo import fetch_all_yahoo_nhl_players

logger = logging.getLogger(__name__)

# ESPN slot ID → position string
# Verified at: https://fantasy.espn.com/apis/v3/games/fhl/players
ESPN_POSITION_MAP: dict[int, str] = {
    1: "C",
    2: "LW",
    3: "RW",
    4: "D",
    5: "G",
    6: "UTIL",
    10: "F",    # Forward (generic)
    # 7 = BN (bench) — excluded
    # 8 = IR — excluded
    # 9 = IR+ — excluded
}

ESPN_PLAYERS_URL = (
    "https://fantasy.espn.com/apis/v3/games/fhl/players"
    "?scoringPeriodId=0&view=players_wl"
)


def map_espn_positions(eligible_slots: list[int]) -> list[str]:
    """Map ESPN eligible slot IDs to position strings, deduplicating."""
    seen: set[str] = set()
    result: list[str] = []
    for slot_id in eligible_slots:
        pos = ESPN_POSITION_MAP.get(slot_id)
        if pos and pos not in seen:
            seen.add(pos)
            result.append(pos)
    return result


def upsert_platform_positions(
    db: Any, player_id: str, platform: str, positions: list[str]
) -> None:
    """Upsert a player_platform_positions row."""
    db.table("player_platform_positions").upsert(
        {"player_id": player_id, "platform": platform, "positions": positions},
        on_conflict="player_id,platform",
    ).execute()


def _fetch_espn_players() -> list[dict[str, Any]]:
    """Fetch all NHL players from ESPN Fantasy API (no auth needed)."""
    resp = httpx.get(ESPN_PLAYERS_URL, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    # ESPN wraps player data under "players" key
    return data.get("players", [])


def ingest_espn_positions(db: Any) -> int:
    """Ingest position eligibility from ESPN and upsert to player_platform_positions."""
    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id").execute().data
    matcher = PlayerMatcher(players, aliases)

    espn_players = _fetch_espn_players()
    upserted = 0
    unmatched = 0

    for ep in espn_players:
        full_name = ep.get("fullName", "")
        if not full_name:
            continue

        player_id = matcher.resolve(full_name)
        if player_id is None:
            unmatched += 1
            continue

        eligible_slots = ep.get("eligibleSlots", [])
        positions = map_espn_positions(eligible_slots)
        if not positions:
            continue

        upsert_platform_positions(db, player_id, "espn", positions)
        upserted += 1

    logger.info("ESPN positions: upserted=%d unmatched=%d", upserted, unmatched)
    return upserted


def ingest_yahoo_positions(db: Any) -> int:
    """Ingest position eligibility from Yahoo Fantasy API.

    Requires YAHOO_OAUTH_REFRESH_TOKEN in config.
    Reuses OAuth2 setup from Yahoo projection scraper.
    Returns 0 if no token configured.
    """
    from core.config import settings
    if not settings.yahoo_oauth_refresh_token:
        logger.warning("Yahoo positions: no OAuth token — skipping")
        return 0

    try:
        yahoo_players = fetch_all_yahoo_nhl_players(settings.yahoo_oauth_refresh_token)
    except Exception as exc:
        logger.error("Yahoo positions fetch failed: %s", exc)
        return 0

    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id").execute().data
    matcher = PlayerMatcher(players, aliases)

    upserted = 0
    for yp in yahoo_players:
        name = yp.get("name", {}).get("full", "")
        player_id = matcher.resolve(name)
        if player_id is None:
            continue
        positions = [
            ep["position"]
            for ep in yp.get("eligible_positions", [])
            if ep["position"] not in ("BN", "IL", "IL+")
        ]
        if positions:
            upsert_platform_positions(db, player_id, "yahoo", positions)
            upserted += 1

    logger.info("Yahoo positions: upserted %d", upserted)
    return upserted


def ingest_fantrax_positions(db: Any) -> int:
    """Ingest position eligibility from Fantrax. Returns 0 if no session token."""
    from core.config import settings
    if not settings.fantrax_session_token:
        logger.warning("Fantrax positions: no session token — skipping")
        return 0

    # TODO: Implement after Fantrax API investigation (see Fantrax scraper)
    logger.info("Fantrax positions: not yet implemented — skipping")
    return 0


if __name__ == "__main__":
    from core.dependencies import get_db
    db = get_db()
    total = ingest_espn_positions(db) + ingest_yahoo_positions(db) + ingest_fantrax_positions(db)
    print(f"Total platform positions upserted: {total}")
