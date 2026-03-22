from __future__ import annotations

import logging
from datetime import date
from typing import Any

PROJECTION_WINDOW: int = 3
SEASON_WEIGHTS: list[float] = [0.5, 0.3, 0.2]  # index 0 = most recent
TOI_THRESHOLD: float = 5.0  # toi_ev per game minimum (300 ES-min / 60 games)

_WEIGHTED_RATE_STATS: list[str] = [
    "icf_per60",
    "ixg_per60",
    "xgf_pct_5v5",
    "cf_pct_adj",
    "scf_per60",
    "scf_pct",
    "p1_per60",
    "toi_ev",
    "toi_pp",
    "toi_sh",
]

logger = logging.getLogger(__name__)


def _apply_weighted_rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute 3-year weighted averages for rate stats.

    Args:
        rows: Season rows for one player, sorted newest-first (from repository).

    Returns:
        Dict with one weighted-average entry per stat in _WEIGHTED_RATE_STATS,
        plus ``_qualifying_count`` (int: number of seasons that passed TOI filter).
        Stats that are null in all qualifying rows → None.
    """
    # Step 1: filter to seasons passing the TOI threshold
    qualifying = [r for r in rows if (r.get("toi_ev") or 0.0) >= TOI_THRESHOLD]

    result: dict[str, Any] = {stat: None for stat in _WEIGHTED_RATE_STATS}
    result["_qualifying_count"] = len(qualifying)

    if not qualifying:
        return result

    # Step 2: take raw SEASON_WEIGHTS for qualifying count, renormalize
    raw_weights = SEASON_WEIGHTS[: len(qualifying)]
    weight_total = sum(raw_weights)
    normalized = [w / weight_total for w in raw_weights]

    # Step 3: per-stat weighted average (further renormalize for per-stat nulls)
    for stat in _WEIGHTED_RATE_STATS:
        stat_pairs = [
            (normalized[i], row[stat])
            for i, row in enumerate(qualifying)
            if row.get(stat) is not None
        ]
        if not stat_pairs:
            result[stat] = None
            continue

        # Renormalize weights for non-null rows of this stat
        stat_weight_total = sum(w for w, _ in stat_pairs)
        result[stat] = sum((w / stat_weight_total) * v for w, v in stat_pairs)

    return result


def _compute_aliases(
    weighted: dict[str, Any],
    current: dict[str, Any],
    prev: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute derived alias features from weighted rates and raw rows.

    Args:
        weighted: Output of _apply_weighted_rates (weighted averages).
        current: Raw row for the current season (rows[0]).
        prev: Raw row for the prior season (rows[1]) or None.

    Returns:
        Dict of alias features ready to be merged into the player feature dict.
    """
    # TOI aliases
    aliases: dict[str, Any] = {
        "toi_ev_per_game": weighted.get("toi_ev"),
        "toi_pp_per_game": weighted.get("toi_pp"),
        "toi_sh_per_game": weighted.get("toi_sh"),
    }

    # SH% delta (current season)
    sh_pct = current.get("sh_pct")
    sh_pct_career = current.get("sh_pct_career_avg")
    aliases["sh_pct_delta"] = (
        sh_pct - sh_pct_career if sh_pct is not None and sh_pct_career is not None else None
    )

    # Pass-through current-season features
    aliases["g_minus_ixg"] = current.get("g_minus_ixg")
    aliases["g_per60"] = current.get("g_per60")
    # NOTE: ixg_per60_curr is the RAW current-season value used by signal rules.
    # weighted["ixg_per60"] is the 3-year weighted average used as a model feature.
    # Signal rules MUST use ixg_per60_curr, not ixg_per60.
    aliases["ixg_per60_curr"] = current.get("ixg_per60")

    # Age: years from date_of_birth to Oct 1 of the season year
    dob_str = current.get("date_of_birth")
    season = current.get("season")
    if dob_str and season:
        dob = date.fromisoformat(dob_str)
        season_start = date(int(season), 10, 1)
        aliases["age"] = (
            season_start.year
            - dob.year
            - ((season_start.month, season_start.day) < (dob.month, dob.day))
        )
    else:
        aliases["age"] = None

    # Delta features (require prior season)
    aliases["icf_per60_delta"] = (
        current["icf_per60"] - prev["icf_per60"]
        if prev is not None
        and current.get("icf_per60") is not None
        and prev.get("icf_per60") is not None
        else None
    )
    aliases["pp_unit_change"] = (
        "PP2→PP1"
        if prev is not None and current.get("pp_unit") == 1 and prev.get("pp_unit") == 2
        else None
    )

    # Disabled in Phase 3c — primary_assists counting stat not in schema (D8)
    aliases["a2_pct_of_assists"] = None

    return aliases


def _compute_breakout_signals(features: dict[str, Any]) -> dict[str, bool]:
    """Evaluate all 8 breakout detection rules.

    Missing inputs (None) always produce False — never raises.
    Signals use ixg_per60_curr (current season), NOT the weighted ixg_per60.
    """

    def _safe(val: Any) -> bool:
        return bool(val) if val is not None else False

    g_per60 = features.get("g_per60")
    ixg_curr = features.get("ixg_per60_curr")
    sh_delta = features.get("sh_pct_delta")
    icf_delta = features.get("icf_per60_delta")
    age = features.get("age")
    xgf = features.get("xgf_pct_5v5")
    pdo = features.get("pdo")
    elc = features.get("elc_flag")
    toi_ev = features.get("toi_ev_per_game")

    return {
        "g_below_ixg": (g_per60 is not None and ixg_curr is not None and g_per60 < ixg_curr * 0.85),
        "sh_pct_below_career": sh_delta is not None and sh_delta < -0.03,
        "rising_shot_gen": icf_delta is not None and icf_delta > 0.5,
        "pp_promotion": features.get("pp_unit_change") == "PP2→PP1",
        "prime_age_window": age is not None and 20 <= age <= 25,
        "strong_underlying": xgf is not None and xgf > 52.0,
        "bad_luck_pdo": pdo is not None and pdo < 0.975,
        "elc_deployed": _safe(elc) and toi_ev is not None and toi_ev >= 14.0,
    }


def _compute_regression_signals(features: dict[str, Any]) -> dict[str, bool]:
    """Evaluate all 7 regression risk detection rules.

    Missing inputs (None) always produce False — never raises.
    g_above_ixg fires for all players — no elite finisher exemption (D5).
    high_secondary_pct always False — a1 counting stat not in schema (D8).
    Signals use ixg_per60_curr (current season), NOT the weighted ixg_per60.
    """
    g_per60 = features.get("g_per60")
    ixg_curr = features.get("ixg_per60_curr")
    sh_delta = features.get("sh_pct_delta")
    pdo = features.get("pdo")
    oi_sh_pct = features.get("oi_sh_pct")
    age = features.get("age")
    position = features.get("position")
    icf_delta = features.get("icf_per60_delta")

    return {
        "g_above_ixg": (g_per60 is not None and ixg_curr is not None and g_per60 > ixg_curr * 1.20),
        "sh_pct_above_career": sh_delta is not None and sh_delta > 0.04,
        "high_pdo": pdo is not None and pdo > 1.025,
        "high_oi_sh_pct": oi_sh_pct is not None and oi_sh_pct > 0.11,
        # D8: primary_assists counting stat not in schema; disabled for Phase 3c
        "high_secondary_pct": False,
        # DB stores NHL.com canonical positions: C/LW/RW for forwards — NOT "F"
        "age_declining": age is not None and age > 30 and position in {"C", "LW", "RW"},
        "declining_shot_gen": icf_delta is not None and icf_delta < -0.5,
    }


def _compute_projection_tier(signal_count: int) -> str | None:
    """Map signal count to tier string.

    HIGH = 4+ signals, MEDIUM = 3, LOW = 2, None = <2.
    """
    if signal_count >= 4:
        return "HIGH"
    if signal_count == 3:
        return "MEDIUM"
    if signal_count == 2:
        return "LOW"
    return None


def build_feature_matrix(
    grouped_stats: dict[str, list[dict[str, Any]]],
    season: int,
) -> list[dict[str, Any]]:
    """Assemble the feature matrix from grouped player_stats rows.

    Args:
        grouped_stats: Output of PlayerStatsRepository.get_seasons_grouped().
                       {player_id: [current_row, y1_row, y2_row]} newest-first.
        season: The requested season year (e.g. 2025). Used to detect players
                missing a current-season row (injured, in minors, or retired).

    Returns:
        List of feature dicts, one per player, ordered by player_id ascending.
        Each dict includes two eligibility flags for downstream filtering:
          - ``stale_season``: True when the player has no row for the requested season
            (injured, in minors, or retired). Training pipeline should exclude these
            until player_status schema is added (Notion backlog).
          - ``position_type``: "goalie" | "skater". Training pipeline should route
            goalies to a separate model (goalie model is Notion backlog).
        Players with 0 qualifying seasons after TOI filter are excluded entirely.
    """
    output: list[dict[str, Any]] = []

    for player_id in sorted(grouped_stats.keys()):
        rows = grouped_stats[player_id]
        if not rows:
            continue

        # Detect stale current-season row: player has no row for the requested season.
        # Possible reasons: injured to start season, in minors (with NHL history), or retired.
        # Retired/minors detection requires player_status schema addition (Notion backlog).
        # For now, fall back to most recent available row for all cases.
        if rows[0].get("season") != season:
            logger.warning(
                "player %s: missing current-season row for %d; "
                "falling back to most recent season %s (injured/minors/retired — "
                "add player_status to players table for full detection)",
                player_id,
                season,
                rows[0].get("season"),
            )

        # Step 1: Weighted rates (TOI-filtered)
        weighted = _apply_weighted_rates(rows)
        qualifying_count = weighted.pop("_qualifying_count")

        if qualifying_count == 0:
            logger.warning("player %s excluded: 0 qualifying seasons after TOI filter", player_id)
            continue

        current = rows[0]
        prev = rows[1] if len(rows) > 1 else None
        stale_season = current.get("season") != season
        position_type = "goalie" if current.get("position") == "G" else "skater"

        # Step 2: Aliases (use original unfiltered rows)
        aliases = _compute_aliases(weighted, current, prev)

        # Step 3: Build working features dict for signal evaluation
        features: dict[str, Any] = {
            **weighted,
            **aliases,
            # Pass-through current-season fields needed by signals
            "pdo": current.get("pdo"),
            "pp_unit": current.get("pp_unit"),
            "oi_sh_pct": current.get("oi_sh_pct"),
            "elc_flag": current.get("elc_flag"),
            "contract_year_flag": current.get("contract_year_flag"),
            "post_extension_flag": current.get("post_extension_flag"),
            "position": current.get("position"),
        }

        # Step 4: Signals
        breakout_signals = _compute_breakout_signals(features)
        regression_signals = _compute_regression_signals(features)

        breakout_count = sum(breakout_signals.values())
        regression_count = sum(regression_signals.values())

        # Step 5: Assemble final feature dict
        output.append(
            {
                "player_id": player_id,
                "season": current.get("season"),
                # Eligibility flags — for training pipeline filtering
                "stale_season": stale_season,
                "position_type": position_type,
                # Weighted rate features
                "icf_per60": weighted.get("icf_per60"),
                "ixg_per60": weighted.get("ixg_per60"),
                "xgf_pct_5v5": weighted.get("xgf_pct_5v5"),
                "cf_pct_adj": weighted.get("cf_pct_adj"),
                "scf_per60": weighted.get("scf_per60"),
                "scf_pct": weighted.get("scf_pct"),
                "p1_per60": weighted.get("p1_per60"),
                "toi_ev": weighted.get("toi_ev"),
                "toi_pp": weighted.get("toi_pp"),
                "toi_sh": weighted.get("toi_sh"),
                "toi_ev_per_game": aliases.get("toi_ev_per_game"),
                "toi_pp_per_game": aliases.get("toi_pp_per_game"),
                "toi_sh_per_game": aliases.get("toi_sh_per_game"),
                # Current-season pass-throughs
                "g_per60": aliases.get("g_per60"),
                "ixg_per60_curr": aliases.get("ixg_per60_curr"),
                "g_minus_ixg": aliases.get("g_minus_ixg"),
                "sh_pct_delta": aliases.get("sh_pct_delta"),
                "pdo": current.get("pdo"),
                "pp_unit": current.get("pp_unit"),
                "oi_sh_pct": current.get("oi_sh_pct"),
                "elc_flag": current.get("elc_flag"),
                "contract_year_flag": current.get("contract_year_flag"),
                "post_extension_flag": current.get("post_extension_flag"),
                "age": aliases.get("age"),
                "position": current.get("position"),
                # Delta features
                "icf_per60_delta": aliases.get("icf_per60_delta"),
                "pp_unit_change": aliases.get("pp_unit_change"),
                "a2_pct_of_assists": aliases.get("a2_pct_of_assists"),
                # Signal outputs
                "breakout_signals": breakout_signals,
                "regression_signals": regression_signals,
                "breakout_count": breakout_count,
                "regression_count": regression_count,
                "breakout_tier": _compute_projection_tier(breakout_count),
                "regression_tier": _compute_projection_tier(regression_count),
            }
        )

    return output
