"""Scoring config validation — enforces double-counting rules."""
from __future__ import annotations


def validate_scoring_config(stat_weights: dict[str, float]) -> None:
    """Raise ValueError if stat_weights double-counts PP or SH stats.

    Rules:
      - PPP and PPG/PPA cannot both be non-zero
      - SHP and SHG/SHA cannot both be non-zero
    """
    ppp = stat_weights.get("ppp", 0)
    ppg = stat_weights.get("ppg", 0)
    ppa = stat_weights.get("ppa", 0)
    shp = stat_weights.get("shp", 0)
    shg = stat_weights.get("shg", 0)
    sha = stat_weights.get("sha", 0)

    if ppp and ppg:
        raise ValueError(
            "Cannot score both PPP and PPG simultaneously — this double-counts power play goals"
        )
    if ppp and ppa:
        raise ValueError(
            "Cannot score both PPP and PPA simultaneously — this double-counts power play assists"
        )
    if shp and shg:
        raise ValueError(
            "Cannot score both SHP and SHG simultaneously — this double-counts short-handed goals"
        )
    if shp and sha:
        raise ValueError(
            "Cannot score both SHP and SHA simultaneously — this double-counts short-handed assists"
        )
