"""
Projection aggregation service — pure functions, no DB access.

Pipeline:
  1. compute_weighted_stats()   — weighted average per stat across sources
  2. apply_scoring_config()     — stats × scoring weights → fantasy points
  3. compute_vorp()             — fantasy points → VORP per position
  4. aggregate_projections()    — top-level orchestrator
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

# All stat columns in player_projections (skater + goalie)
SKATER_STATS: list[str] = [
    "g", "a", "plus_minus", "pim", "ppg", "ppa", "ppp",
    "shg", "sha", "shp", "sog", "fow", "fol", "hits", "blocks", "gp",
]
GOALIE_STATS: list[str] = ["gs", "w", "l", "ga", "sa", "sv", "sv_pct", "so", "otl"]
ALL_STATS: list[str] = SKATER_STATS + GOALIE_STATS

# Positions that count toward VORP replacement-level thresholds.
# UTIL and BN are excluded per spec §7.3.
_VORP_POSITION_SLOTS = frozenset({"C", "LW", "RW", "D", "G"})


def compute_weighted_stats(
    rows: list[dict[str, Any]],
) -> dict[str, float | None]:
    """Compute weighted average per stat for a single player across sources.

    Args:
        rows: List of source rows for one player. Each dict must have
              ``source_weight`` (float) and one key per stat column.
              null stat value = source did not project that stat.

    Returns:
        Dict mapping stat_name → weighted average (None if no source projected it).
        Also includes ``_source_count``: count of sources that projected any stat.
    """
    weighted_sum: dict[str, float] = defaultdict(float)
    total_weight: dict[str, float] = defaultdict(float)

    sources_with_any_stat: set[str] = set()

    for row in rows:
        w = row.get("source_weight", 0.0)
        if w <= 0:
            continue
        source = row.get("source_name", "")
        for stat in ALL_STATS:
            val = row.get(stat)
            if val is not None:
                weighted_sum[stat] += val * w
                total_weight[stat] += w
                sources_with_any_stat.add(source)

    result: dict[str, float | None] = {}
    for stat in ALL_STATS:
        if total_weight[stat] > 0:
            result[stat] = weighted_sum[stat] / total_weight[stat]
        else:
            result[stat] = None

    result["_source_count"] = len(sources_with_any_stat)
    return result


def apply_scoring_config(
    stats: dict[str, float | None],
    scoring_config: dict[str, float],
) -> float:
    """Convert projected stats to fantasy points using a scoring config.

    Args:
        stats:          stat_name → weighted average (None treated as 0).
        scoring_config: stat_name → fantasy point weight.
                        Keys not in stats are ignored.

    Returns:
        Projected fantasy points (float). Returns 0.0 for all-null stats.
    """
    total = 0.0
    for stat, weight in scoring_config.items():
        val = stats.get(stat)
        if val is not None and weight:
            total += val * weight
    return total


def compute_vorp(
    players: list[dict[str, Any]],
    league_profile: dict[str, Any],
) -> dict[str, float | None]:
    """Compute Value Over Replacement Player for each player.

    Args:
        players: List of player dicts, each with:
                   - player_id: str
                   - default_position: str  (NHL.com canonical: C, LW, RW, D, G)
                   - projected_fantasy_points: float | None
        league_profile: Dict with num_teams (int) and roster_slots (dict[str, int]).
                        roster_slots keys should be position codes matching
                        players.default_position.

    Returns:
        Dict of player_id → VORP (float | None).
        None when: player has null FP, position not in _VORP_POSITION_SLOTS,
        or position group has no roster slot.
    """
    num_teams: int = league_profile["num_teams"]
    roster_slots: dict[str, int] = league_profile.get("roster_slots", {})

    # Group by NHL.com position
    by_position: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in players:
        by_position[p["default_position"]].append(p)

    # Sort each position group descending by FP (nulls last)
    for pos_players in by_position.values():
        pos_players.sort(
            key=lambda p: (
                p["projected_fantasy_points"] is None,
                -(p["projected_fantasy_points"] or 0),
            )
        )

    result: dict[str, float | None] = {}

    for player in players:
        pid = player["player_id"]
        pos = player["default_position"]
        fp = player["projected_fantasy_points"]

        if fp is None:
            result[pid] = None
            continue

        # Defensive guard: UTIL and BN are not valid VORP position groups
        if pos not in _VORP_POSITION_SLOTS:
            result[pid] = None
            continue

        slots = roster_slots.get(pos, 0)
        if slots == 0:
            result[pid] = None
            continue

        # replacement level = player at index (num_teams × slots), 0-based
        threshold_idx = num_teams * slots
        pos_group = by_position[pos]
        eligible = [p for p in pos_group if p["projected_fantasy_points"] is not None]

        if not eligible:
            result[pid] = None
            continue

        # If fewer players than threshold, use last available
        replacement_idx = min(threshold_idx, len(eligible) - 1)
        replacement_fp = eligible[replacement_idx]["projected_fantasy_points"]

        result[pid] = fp - replacement_fp  # may be negative

    return result


def aggregate_projections(
    rows: list[dict[str, Any]],
    source_weights: dict[str, float],
    scoring_config: dict[str, float],
    league_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Orchestrate the full projection aggregation pipeline.

    Args:
        rows:           Raw DB rows from ProjectionRepository.get_by_season().
                        Each row is one (player, source) pair with all stat cols.
        source_weights: User's source weights — {source_name: weight}.
                        Sources absent from this dict are excluded.
        scoring_config: Scoring weights — {stat_name: fantasy_pt_weight}.
        league_profile: Optional. If provided, VORP is computed per position.

    Returns:
        List of player dicts sorted by projected_fantasy_points descending
        (nulls last). Each dict matches the RankedPlayer schema.
    """
    # 1. Group rows by player_id, injecting source_weight from user's config
    player_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    player_meta: dict[str, dict[str, Any]] = {}

    for row in rows:
        source_name = row.get("sources", {}).get("name", "")
        weight = source_weights.get(source_name, 0.0)
        if weight <= 0:
            pass  # still record meta for this player
        else:
            pid = row["player_id"]
            player_rows[pid].append({**row, "source_name": source_name, "source_weight": weight})

        pid = row["player_id"]
        if pid not in player_meta:
            players_join = row.get("players", {})
            platform_pos = row.get("player_platform_positions") or []
            schedule = row.get("schedule_scores") or []
            player_meta[pid] = {
                "player_id": pid,
                "name": players_join.get("name"),
                "team": players_join.get("team"),
                "default_position": players_join.get("position"),
                "platform_positions": platform_pos[0].get("positions", []) if platform_pos else [],
                "schedule_score": schedule[0].get("schedule_score") if schedule else None,
                "off_night_games": schedule[0].get("off_night_games") if schedule else None,
            }

    # 2. Compute weighted stats and fantasy points per player
    all_pids = set(player_meta.keys())
    aggregated: list[dict[str, Any]] = []

    for pid in all_pids:
        meta = player_meta[pid]
        p_rows = player_rows.get(pid, [])

        if p_rows:
            stats = compute_weighted_stats(p_rows)
            source_count = int(stats.pop("_source_count", 0))
            # Only count as real FP if at least one source contributed
            fp_raw = apply_scoring_config(stats, scoring_config)
            fp: float | None = fp_raw if source_count > 0 else None
        else:
            stats = {s: None for s in ALL_STATS}
            source_count = 0
            fp = None

        aggregated.append({
            **meta,
            "projected_fantasy_points": fp,
            "vorp": None,  # filled in step 3
            "source_count": source_count,
            "projected_stats": {s: stats.get(s) for s in ALL_STATS},
            "breakout_score": None,
            "regression_risk": None,
        })

    # 3. Compute VORP if league profile provided
    if league_profile:
        vorps = compute_vorp(aggregated, league_profile)
        for player in aggregated:
            player["vorp"] = vorps.get(player["player_id"])

    # 4. Sort by fantasy points descending (nulls last)
    aggregated.sort(
        key=lambda p: (
            p["projected_fantasy_points"] is None,
            -(p["projected_fantasy_points"] or 0),
        )
    )

    # 5. Assign composite_rank
    for i, player in enumerate(aggregated, 1):
        player["composite_rank"] = i

    return aggregated
