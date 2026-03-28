from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client

PROJECTION_WINDOW: int = 3

_STAT_COLUMNS = (
    "player_id, season, "
    "toi_ev, toi_pp, toi_sh, "
    "icf_per60, ixg_per60, xgf_pct_5v5, cf_pct_adj, "
    "scf_per60, scf_pct, p1_per60, "
    "hits_per60, blocks_per60, "
    "pdo, sh_pct, sh_pct_career_avg, g_minus_ixg, g_per60, "
    "oi_sh_pct, pp_unit, "
    "elc_flag, contract_year_flag, post_extension_flag"
)


class PlayerStatsRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def get_seasons_grouped(
        self,
        season: int,
        window: int = PROJECTION_WINDOW,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return player_stats rows for the given season window, grouped by player_id.

        Returns:
            {player_id: [row_current, row_y1, row_y2]} sorted newest-first.
            Each row has players.date_of_birth and players.position flattened in.
            Players with fewer than `window` seasons return however many exist.
        """
        seasons = list(range(season - window + 1, season + 1))

        result = (
            self._db.table("player_stats")
            .select(f"{_STAT_COLUMNS}, players!inner(date_of_birth, position)")
            .in_("season", seasons)
            .order("season", desc=True)
            .execute()
        )

        # Group by player_id; flatten players join
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for raw in result.data:
            players_join = raw.pop("players", {})
            row = {**raw, **players_join}
            grouped[row["player_id"]].append(row)

        # Sort each player's rows newest-first
        for rows in grouped.values():
            rows.sort(key=lambda r: r["season"], reverse=True)

        return dict(grouped)

    def get_all_seasons_grouped(self) -> dict[str, list[dict[str, Any]]]:
        """Return ALL player_stats rows for ALL players, grouped by player_id.

        Unlike get_seasons_grouped(), this method has no season window cap and
        returns every historical row available. Used only by ml/train.py.

        Uses LEFT JOIN on players table so debutants (players with no `players`
        record) are included; their position and date_of_birth will be None.

        Returns:
            {player_id: [rows sorted newest-first]}
        """
        result = (
            self._db.table("player_stats")
            .select(f"{_STAT_COLUMNS}, players(date_of_birth, position)")
            .order("season", desc=True)
            .execute()
        )

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for raw in result.data:
            players_join = raw.pop("players", None) or {}
            row = {**raw, **players_join}
            grouped[row["player_id"]].append(row)

        for rows in grouped.values():
            rows.sort(key=lambda r: r["season"], reverse=True)

        return dict(grouped)
