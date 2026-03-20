"""
Rankings computation service.

Algorithm (per CLAUDE.md):
  1. Per-source rank → normalise to 0–1 score
  2. Apply user-defined weights
  3. Compute weighted average per player
  4. Sort descending by composite score

Missing sources degrade gracefully: only sources that have data for a player
contribute to that player's total weight, so partial coverage is handled
automatically without the caller needing to redistribute weights.
"""

from __future__ import annotations

from typing import Any


def compute_weighted_rankings(
    source_rankings: dict[str, list[dict[str, Any]]],
    weights: dict[str, float],
) -> list[dict[str, Any]]:
    """Compute composite rankings from per-source data and user weights.

    Args:
        source_rankings: Mapping of source_name → list of player ranking dicts.
            Each dict must contain at least ``player_id``, ``rank``, ``name``.
            Additional fields (``team``, ``position``) are preserved on the
            first encountered entry for each player.
        weights: Mapping of source_name → weight value (any positive float).
            Weights are normalised internally; they need not sum to any
            specific value.  Sources absent from weights (or with weight ≤ 0)
            are ignored.

    Returns:
        List of player dicts sorted by ``composite_score`` descending.
        Each dict includes ``composite_rank``, ``composite_score``, and
        ``source_ranks`` (dict of source_name → original rank for transparency).
    """
    player_data: dict[str, dict[str, Any]] = {}
    player_weighted_sum: dict[str, float] = {}
    player_total_weight: dict[str, float] = {}
    player_source_ranks: dict[str, dict[str, int]] = {}

    for source_name, rankings in source_rankings.items():
        source_weight = weights.get(source_name, 0.0)
        if source_weight <= 0 or not rankings:
            continue

        n = len(rankings)
        for entry in rankings:
            pid = entry["player_id"]
            rank = entry["rank"]

            # Normalise: rank 1 → 1.0, rank n → ~0.0
            score = 1.0 - (rank - 1) / n if n > 1 else 1.0

            if pid not in player_data:
                # Store stable player metadata from first source seen
                player_data[pid] = {k: v for k, v in entry.items() if k not in ("rank", "score")}
                player_weighted_sum[pid] = 0.0
                player_total_weight[pid] = 0.0
                player_source_ranks[pid] = {}

            player_weighted_sum[pid] += score * source_weight
            player_total_weight[pid] += source_weight
            player_source_ranks[pid][source_name] = rank

    results: list[dict[str, Any]] = []
    for pid, data in player_data.items():
        total_w = player_total_weight[pid]
        if total_w > 0:
            composite_score = player_weighted_sum[pid] / total_w
            results.append(
                {
                    **data,
                    "composite_score": round(composite_score, 4),
                    "source_ranks": player_source_ranks[pid],
                }
            )

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, row in enumerate(results, 1):
        row["composite_rank"] = i

    return results


def flatten_db_rankings(
    db_rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Convert raw DB join rows into the source_rankings dict expected by
    ``compute_weighted_rankings``.

    Each DB row has the shape returned by RankingsRepository.get_by_season():
      {
        "rank": int,
        "season": str,
        "players": {"id": str, "name": str, "team": str, "position": str},
        "sources": {"name": str, "display_name": str},
      }
    """
    source_rankings: dict[str, list[dict[str, Any]]] = {}

    for row in db_rows:
        source_name = row["sources"]["name"]
        player = row["players"]
        entry = {
            "player_id": player["id"],
            "name": player["name"],
            "team": player.get("team"),
            "position": player.get("position"),
            "rank": row["rank"],
        }
        source_rankings.setdefault(source_name, []).append(entry)

    return source_rankings
