# apps/api/scrapers/matching.py
"""
Player name resolution for projection scrapers.

Uses a three-level lookup:
  1. Exact match (normalised to lowercase, stripped)
  2. player_aliases lookup (pre-seeded cross-source name variants)
  3. rapidfuzz token_sort_ratio fuzzy match against canonical player names

Usage:
    matcher = PlayerMatcher(players=db_players, aliases=db_aliases)
    player_id = matcher.resolve("J. Kotkaniemi")  # → UUID or None
"""
from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process


class PlayerMatcher:
    def __init__(
        self,
        players: list[dict[str, Any]],
        aliases: list[dict[str, Any]],
    ) -> None:
        # Exact match index: normalised name → player_id
        self._exact: dict[str, str] = {
            p["name"].strip().lower(): p["id"] for p in players
        }
        # Alias index: normalised alias → player_id
        self._alias: dict[str, str] = {
            a["alias_name"].strip().lower(): a["player_id"] for a in aliases
        }
        # Fuzzy match corpus: list of canonical names in same order as _players
        self._players = players
        self._names: list[str] = [p["name"] for p in players]

    def resolve(self, raw_name: str, threshold: int = 85) -> str | None:
        """Resolve a raw player name string to a canonical player_id.

        Returns None if no match at or above ``threshold``.
        """
        if not raw_name or not raw_name.strip():
            return None

        normalised = raw_name.strip().lower()

        # 1. Exact
        if normalised in self._exact:
            return self._exact[normalised]

        # 2. Alias
        if normalised in self._alias:
            return self._alias[normalised]

        # 3. Fuzzy
        if not self._names:
            return None

        result = process.extractOne(
            raw_name,
            self._names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )
        if result is None:
            return None

        matched_name, _score, idx = result
        return self._players[idx]["id"]
