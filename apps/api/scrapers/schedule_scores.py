# apps/api/scrapers/schedule_scores.py
"""
NHL schedule scores ingestion.

Pulls the NHL regular season schedule from the NHL.com API, computes
each player's off-night game count (games played when ≤ threshold teams
are playing), normalises to a 0–1 score, and upserts to schedule_scores.

Off-night games are a positive indicator — fewer teams playing means less
rested opponents and reduced goaltending depth on those nights.

Usage:
    python -m scrapers.schedule_scores
"""
from __future__ import annotations

import asyncio
import datetime
import logging
from collections import defaultdict
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Games where ≤ this many NHL teams play are considered "off-nights"
OFF_NIGHT_THRESHOLD = 10

NHL_SCHEDULE_URL = "https://api-web.nhle.com/v1/schedule/{date}"


def count_off_night_games(
    player_game_dates: set[str],
    schedule: list[dict[str, Any]],
    off_night_threshold: int = OFF_NIGHT_THRESHOLD,
) -> int:
    """Return the number of player game dates that fall on off-nights.

    Args:
        player_game_dates: Set of ISO date strings when this player's team plays.
        schedule: List of {"date": str, "teams": list[str]} across the season.
        off_night_threshold: Days with ≤ this many teams are off-nights.
    """
    date_team_count: dict[str, int] = {g["date"]: len(g["teams"]) for g in schedule}
    return sum(
        1
        for date in player_game_dates
        if date_team_count.get(date, 0) <= off_night_threshold
    )


def compute_schedule_score(off_night_games: int, total_games: int) -> float:
    """Normalise off-night game count to a 0–1 score.

    Uses the fraction of games that are off-night games.
    Returns 0.0 when total_games is 0.
    """
    if total_games == 0:
        return 0.0
    return round(off_night_games / total_games, 4)


async def _fetch_season_schedule(season: str) -> list[dict[str, Any]]:
    """Fetch all regular-season games from NHL.com API for a given season.

    Returns a list of {"date": "YYYY-MM-DD", "teams": ["EDM", "TOR", ...]}
    for each game day.
    """
    # NHL season typically Oct 1 – Apr 30
    start_year = int(season.split("-")[0])

    games_by_date: dict[str, set[str]] = defaultdict(set)

    async with httpx.AsyncClient(timeout=30.0) as client:
        current = datetime.date(start_year, 10, 1)
        end = datetime.date(start_year + 1, 5, 1)

        while current <= end:
            url = NHL_SCHEDULE_URL.format(date=current.isoformat())
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                for day in data.get("gameWeek", []):
                    date_str = day.get("date", "")
                    for game in day.get("games", []):
                        if game.get("gameType") != 2:  # 2 = regular season
                            continue
                        home = game.get("homeTeam", {}).get("abbrev", "")
                        away = game.get("awayTeam", {}).get("abbrev", "")
                        if home:
                            games_by_date[date_str].add(home)
                        if away:
                            games_by_date[date_str].add(away)
            except Exception as exc:
                logger.warning("Schedule fetch error for %s: %s", current, exc)

            # Advance one week at a time
            current += datetime.timedelta(weeks=1)
            await asyncio.sleep(0.5)

    return [{"date": date, "teams": list(teams)} for date, teams in sorted(games_by_date.items())]


async def ingest(season: str, db: Any) -> None:
    """Fetch schedule, compute per-player scores, upsert to schedule_scores."""
    schedule = await _fetch_season_schedule(season)
    if not schedule:
        logger.warning(
            "Schedule scores: no game days fetched for %s — aborting to preserve existing data",
            season,
        )
        return
    logger.info("Fetched %d game days for %s", len(schedule), season)

    # Build date → teams index
    date_teams: dict[str, set[str]] = {
        g["date"]: set(g["teams"]) for g in schedule
    }

    # Get all players with their team
    players = db.table("players").select("id, team").execute().data

    # Fetch player_stats to know which dates each player's team actually played
    # (Use schedule data to build team → game_dates mapping)
    team_game_dates: dict[str, set[str]] = defaultdict(set)
    for date, teams in date_teams.items():
        for team in teams:
            team_game_dates[team].add(date)

    upserted = 0
    for player in players:
        team = player.get("team", "")
        player_id = player["id"]
        game_dates = team_game_dates.get(team, set())
        total_games = len(game_dates)
        off_night = count_off_night_games(game_dates, schedule)
        score = compute_schedule_score(off_night, total_games)

        db.table("schedule_scores").upsert(
            {
                "player_id": player_id,
                "season": season,
                "off_night_games": off_night,
                "total_games": total_games,
                "schedule_score": score,
            },
            on_conflict="player_id,season",
        ).execute()
        upserted += 1

    logger.info("Schedule scores: upserted %d rows for %s", upserted, season)


if __name__ == "__main__":
    from core.config import settings
    from core.dependencies import get_db
    asyncio.run(ingest(settings.current_season, get_db()))
