# Phase 3c — Feature Engineering Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `repositories/player_stats.py` and `services/feature_engineering.py` — the pure-Python feature matrix pipeline that transforms raw `player_stats` rows into per-player feature dicts for model training (Phase 3d) and nightly inference (Phase 3e).

**Architecture:** Repository fetches 3 seasons of `player_stats` joined with `players` and returns a `dict[player_id, list[row]]` sorted newest-first. The pure service layer receives this grouped dict, applies 3-year weighted averages, computes aliases and signals, and returns `list[dict]` — one per player. No DB access, no pandas, no I/O in the service.

**Tech Stack:** Python 3.11+, FastAPI, Supabase Python client (MagicMock in tests), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-03-22-phase3c-feature-engineering.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `apps/api/repositories/player_stats.py` | CREATE | Multi-season query grouped by player_id |
| `apps/api/services/feature_engineering.py` | CREATE | Pure transforms: weighting, aliasing, signals, tiers |
| `apps/api/tests/repositories/test_player_stats.py` | CREATE | Repo tests (all mocked Supabase client) |
| `apps/api/tests/services/test_feature_engineering.py` | CREATE | Service tests (plain dicts, zero mocks) |

---

## Constants (both files must agree)

```python
PROJECTION_WINDOW: int = 3
SEASON_WEIGHTS: list[float] = [0.5, 0.3, 0.2]  # index 0 = most recent season
TOI_THRESHOLD: float = 5.0  # toi_ev per game; 300 ES-min threshold
```

---

## Task 1: Open Branch

**Files:** none

- [ ] **Step 1: Verify on main, pull latest**

```bash
cd /Users/troyjohnson/projects/pucklogic-ui
git branch --show-current   # must say: main
git pull
```

- [ ] **Step 2: Create feature branch**

```bash
git checkout -b feat/phase3c-feature-engineering
git branch --show-current   # must say: feat/phase3c-feature-engineering
```

- [ ] **Step 3: Confirm working directory**

```bash
cd apps/api
ls repositories/   # should show existing repo files
ls services/       # should show existing service files
```

---

## Task 2: Repository — `PlayerStatsRepository`

**Files:**
- Create: `apps/api/repositories/player_stats.py`
- Create: `apps/api/tests/repositories/test_player_stats.py`

### 2a — Write failing tests first

- [ ] **Step 1: Create test file with all cases**

```python
# apps/api/tests/repositories/test_player_stats.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.player_stats import PlayerStatsRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> PlayerStatsRepository:
    return PlayerStatsRepository(mock_db)


def _configure_db(mock_db: MagicMock, rows: list[dict]) -> None:
    """Wire mock_db so .table().select().in_().execute().data = rows."""
    (
        mock_db.table.return_value
        .select.return_value
        .in_.return_value
        .execute.return_value
    ).data = rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_row(
    player_id: str = "p-mcdavid",
    season: int = 2025,
    toi_ev: float = 21.3,
    icf_per60: float | None = 14.2,
    ixg_per60: float | None = 12.0,
    date_of_birth: str = "1997-01-13",
    position: str = "F",
) -> dict:
    return {
        "player_id": player_id,
        "season": season,
        "toi_ev": toi_ev,
        "toi_pp": 3.5,
        "toi_sh": 0.2,
        "icf_per60": icf_per60,
        "ixg_per60": ixg_per60,
        "xgf_pct_5v5": 55.0,
        "cf_pct_adj": 54.0,
        "scf_per60": 18.0,
        "scf_pct": 53.0,
        "p1_per60": 3.5,
        "pdo": 1.010,
        "sh_pct": 0.115,
        "sh_pct_career_avg": 0.110,
        "g_minus_ixg": 0.5,
        "g_per60": 2.8,
        "oi_sh_pct": 0.095,
        "pp_unit": 1,
        "elc_flag": False,
        "contract_year_flag": False,
        "post_extension_flag": False,
        "players": {
            "date_of_birth": date_of_birth,
            "position": position,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetSeasonsGrouped:
    def test_returns_dict_keyed_by_player_id(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        _configure_db(mock_db, [_make_db_row(player_id="p-mcdavid", season=2025)])
        result = repo.get_seasons_grouped(season=2025)
        assert "p-mcdavid" in result

    def test_single_player_single_season_returns_one_row(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        _configure_db(mock_db, [_make_db_row(player_id="p-mcdavid", season=2025)])
        result = repo.get_seasons_grouped(season=2025)
        assert len(result["p-mcdavid"]) == 1

    def test_multiple_seasons_sorted_newest_first(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        # DB returns in arbitrary order — repo must sort newest-first
        _configure_db(mock_db, [
            _make_db_row(player_id="p-mcdavid", season=2023),
            _make_db_row(player_id="p-mcdavid", season=2025),
            _make_db_row(player_id="p-mcdavid", season=2024),
        ])
        result = repo.get_seasons_grouped(season=2025)
        seasons = [r["season"] for r in result["p-mcdavid"]]
        assert seasons == [2025, 2024, 2023]

    def test_multiple_players_each_grouped_separately(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        _configure_db(mock_db, [
            _make_db_row(player_id="p-mcdavid", season=2025),
            _make_db_row(player_id="p-draisaitl", season=2025),
        ])
        result = repo.get_seasons_grouped(season=2025)
        assert "p-mcdavid" in result
        assert "p-draisaitl" in result
        assert len(result["p-mcdavid"]) == 1
        assert len(result["p-draisaitl"]) == 1

    def test_player_with_one_season_returns_one_row(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        _configure_db(mock_db, [_make_db_row(player_id="p-rookie", season=2025)])
        result = repo.get_seasons_grouped(season=2025, window=3)
        assert len(result["p-rookie"]) == 1

    def test_players_join_flattened_into_row(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        _configure_db(mock_db, [
            _make_db_row(player_id="p-mcdavid", season=2025, date_of_birth="1997-01-13", position="F")
        ])
        result = repo.get_seasons_grouped(season=2025)
        row = result["p-mcdavid"][0]
        assert row["date_of_birth"] == "1997-01-13"
        assert row["position"] == "F"
        assert "players" not in row  # nested dict should be flattened

    def test_queries_correct_season_range(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        _configure_db(mock_db, [])
        repo.get_seasons_grouped(season=2025, window=3)
        # The .in_() call should receive seasons [2023, 2024, 2025]
        in_call_args = mock_db.table.return_value.select.return_value.in_.call_args
        field, seasons = in_call_args[0]
        assert field == "season"
        assert set(seasons) == {2023, 2024, 2025}

    def test_custom_window_queries_correct_seasons(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        _configure_db(mock_db, [])
        repo.get_seasons_grouped(season=2025, window=2)
        in_call_args = mock_db.table.return_value.select.return_value.in_.call_args
        _, seasons = in_call_args[0]
        assert set(seasons) == {2024, 2025}

    def test_empty_result_returns_empty_dict(self, repo: PlayerStatsRepository, mock_db: MagicMock) -> None:
        _configure_db(mock_db, [])
        result = repo.get_seasons_grouped(season=2025)
        assert result == {}
```

- [ ] **Step 2: Run tests — expect ImportError (file doesn't exist yet)**

```bash
cd apps/api
pytest tests/repositories/test_player_stats.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'repositories.player_stats'`

### 2b — Implement repository

- [ ] **Step 3: Create `repositories/player_stats.py`**

```python
# apps/api/repositories/player_stats.py
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
            .select(
                f"{_STAT_COLUMNS}, "
                "players!inner(date_of_birth, position)"
            )
            .in_("season", seasons)
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
```

- [ ] **Step 4: Run tests — all must pass**

```bash
pytest tests/repositories/test_player_stats.py -v
```
Expected: 9 passed, 0 failed.

- [ ] **Step 5: Lint**

```bash
ruff check repositories/player_stats.py && ruff format repositories/player_stats.py
```

- [ ] **Step 6: Commit**

```bash
git add repositories/player_stats.py tests/repositories/test_player_stats.py
git commit -m "feat(3c): PlayerStatsRepository — multi-season grouped query"
```

---

## Task 3: Service Skeleton + `_apply_weighted_rates`

**Files:**
- Create: `apps/api/services/feature_engineering.py` (skeleton)
- Create: `apps/api/tests/services/test_feature_engineering.py` (weighted rates section)

### 3a — Write failing tests

- [ ] **Step 1: Create test file — weighted rates section**

```python
# apps/api/tests/services/test_feature_engineering.py
from __future__ import annotations

import pytest

from services.feature_engineering import (
    PROJECTION_WINDOW,
    SEASON_WEIGHTS,
    TOI_THRESHOLD,
    _apply_weighted_rates,
    _compute_aliases,
    _compute_breakout_signals,
    _compute_projection_tier,
    _compute_regression_signals,
    build_feature_matrix,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RATE_STATS = [
    "icf_per60", "ixg_per60", "xgf_pct_5v5", "cf_pct_adj",
    "scf_per60", "scf_pct", "p1_per60", "toi_ev", "toi_pp", "toi_sh",
]


def _make_row(
    season: int = 2025,
    toi_ev: float = 21.3,
    icf_per60: float | None = 14.0,
    ixg_per60: float | None = 12.0,
    xgf_pct_5v5: float | None = 55.0,
    cf_pct_adj: float | None = 54.0,
    scf_per60: float | None = 18.0,
    scf_pct: float | None = 53.0,
    p1_per60: float | None = 3.5,
    toi_pp: float = 3.5,
    toi_sh: float = 0.2,
    # aliases / pass-through fields
    sh_pct: float | None = 0.115,
    sh_pct_career_avg: float | None = 0.110,
    g_minus_ixg: float | None = 0.5,
    g_per60: float | None = 2.8,
    oi_sh_pct: float | None = 0.095,
    pp_unit: int | None = 1,
    elc_flag: bool = False,
    contract_year_flag: bool = False,
    post_extension_flag: bool = False,
    # players join fields
    date_of_birth: str = "1997-01-13",
    position: str = "C",  # NHL.com canonical: C/LW/RW/D/G — never "F"
) -> dict:
    return {
        "season": season,
        "toi_ev": toi_ev,
        "toi_pp": toi_pp,
        "toi_sh": toi_sh,
        "icf_per60": icf_per60,
        "ixg_per60": ixg_per60,
        "xgf_pct_5v5": xgf_pct_5v5,
        "cf_pct_adj": cf_pct_adj,
        "scf_per60": scf_per60,
        "scf_pct": scf_pct,
        "p1_per60": p1_per60,
        "sh_pct": sh_pct,
        "sh_pct_career_avg": sh_pct_career_avg,
        "g_minus_ixg": g_minus_ixg,
        "g_per60": g_per60,
        "oi_sh_pct": oi_sh_pct,
        "pp_unit": pp_unit,
        "pdo": 1.010,
        "elc_flag": elc_flag,
        "contract_year_flag": contract_year_flag,
        "post_extension_flag": post_extension_flag,
        "date_of_birth": date_of_birth,
        "position": position,
    }


# ---------------------------------------------------------------------------
# Tests: _apply_weighted_rates
# ---------------------------------------------------------------------------


class TestApplyWeightedRates:
    def test_three_seasons_weighted_correctly(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0),
            _make_row(season=2024, toi_ev=20.0, icf_per60=13.0),
            _make_row(season=2023, toi_ev=19.0, icf_per60=11.0),
        ]
        result = _apply_weighted_rates(rows)
        # icf_per60 = 15*0.5 + 13*0.3 + 11*0.2 = 7.5 + 3.9 + 2.2 = 13.6
        assert result["icf_per60"] == pytest.approx(13.6)

    def test_two_seasons_renormalizes_weights(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0),
            _make_row(season=2024, toi_ev=20.0, icf_per60=13.0),
        ]
        result = _apply_weighted_rates(rows)
        # Weights [0.5, 0.3] → renormalized [0.625, 0.375]
        # icf_per60 = 15*0.625 + 13*0.375 = 9.375 + 4.875 = 14.25
        assert result["icf_per60"] == pytest.approx(14.25)

    def test_one_season_returns_that_seasons_value(self) -> None:
        rows = [_make_row(season=2025, toi_ev=21.0, icf_per60=15.0)]
        result = _apply_weighted_rates(rows)
        assert result["icf_per60"] == pytest.approx(15.0)

    def test_season_below_toi_threshold_excluded(self) -> None:
        # toi_ev = 4.9 < TOI_THRESHOLD (5.0) → excluded
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0),
            _make_row(season=2024, toi_ev=4.9, icf_per60=5.0),  # excluded
        ]
        result = _apply_weighted_rates(rows)
        # Only 2025 qualifies; renormalized to weight [1.0]
        assert result["icf_per60"] == pytest.approx(15.0)

    def test_all_seasons_below_threshold_returns_none_stats(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=4.0, icf_per60=15.0),
        ]
        result = _apply_weighted_rates(rows)
        # Player excluded — all rate stats None
        assert result["icf_per60"] is None

    def test_null_stat_excluded_per_stat_only(self) -> None:
        # Season 2024 has null icf_per60 but valid xgf_pct_5v5
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0, xgf_pct_5v5=55.0),
            _make_row(season=2024, toi_ev=20.0, icf_per60=None, xgf_pct_5v5=53.0),
        ]
        result = _apply_weighted_rates(rows)
        # icf_per60: only 2025 contributes → weight [1.0] → 15.0
        assert result["icf_per60"] == pytest.approx(15.0)
        # xgf_pct_5v5: both seasons → [0.625, 0.375] → 55*0.625 + 53*0.375
        assert result["xgf_pct_5v5"] == pytest.approx(55.0 * 0.625 + 53.0 * 0.375)

    def test_all_rows_null_for_stat_returns_none(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=None),
            _make_row(season=2024, toi_ev=20.0, icf_per60=None),
        ]
        result = _apply_weighted_rates(rows)
        assert result["icf_per60"] is None

    def test_all_rate_stats_in_result(self) -> None:
        rows = [_make_row(season=2025, toi_ev=21.0)]
        result = _apply_weighted_rates(rows)
        for stat in _RATE_STATS:
            assert stat in result

    def test_zero_value_is_not_null(self) -> None:
        rows = [_make_row(season=2025, toi_ev=21.0, icf_per60=0.0)]
        result = _apply_weighted_rates(rows)
        assert result["icf_per60"] == pytest.approx(0.0)
        assert result["icf_per60"] is not None

    def test_qualifying_count_zero_when_all_below_threshold(self) -> None:
        rows = [_make_row(season=2025, toi_ev=4.0)]  # below threshold
        result = _apply_weighted_rates(rows)
        assert result["_qualifying_count"] == 0

    def test_qualifying_count_one_when_one_of_two_excluded(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0),
            _make_row(season=2024, toi_ev=4.9, icf_per60=5.0),  # excluded
        ]
        result = _apply_weighted_rates(rows)
        assert result["_qualifying_count"] == 1
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/services/test_feature_engineering.py::TestApplyWeightedRates -v 2>&1 | head -10
```

### 3b — Implement service skeleton + `_apply_weighted_rates`

- [ ] **Step 3: Create `services/feature_engineering.py` with constants + `_apply_weighted_rates`**

```python
# apps/api/services/feature_engineering.py
from __future__ import annotations

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


# Placeholders — implemented in subsequent tasks
def _compute_aliases(
    weighted: dict[str, Any],
    current: dict[str, Any],
    prev: dict[str, Any] | None,
) -> dict[str, Any]:
    raise NotImplementedError


def _compute_breakout_signals(features: dict[str, Any]) -> dict[str, bool]:
    raise NotImplementedError


def _compute_regression_signals(features: dict[str, Any]) -> dict[str, bool]:
    raise NotImplementedError


def _compute_projection_tier(signal_count: int) -> str | None:
    raise NotImplementedError


def build_feature_matrix(
    grouped_stats: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    raise NotImplementedError
```

- [ ] **Step 4: Run weighted-rates tests — all must pass**

```bash
pytest tests/services/test_feature_engineering.py::TestApplyWeightedRates -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add services/feature_engineering.py tests/services/test_feature_engineering.py
git commit -m "feat(3c): _apply_weighted_rates — 3-year weighted average with TOI filter"
```

---

## Task 4: `_compute_aliases`

**Files:** `services/feature_engineering.py`, `tests/services/test_feature_engineering.py`

- [ ] **Step 1: Add alias tests to test file**

```python
# Append to tests/services/test_feature_engineering.py

class TestComputeAliases:
    def test_toi_aliases_renamed(self) -> None:
        weighted = {"toi_ev": 21.3, "toi_pp": 3.5, "toi_sh": 0.2, "icf_per60": 14.0}
        current = _make_row(season=2025)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["toi_ev_per_game"] == pytest.approx(21.3)
        assert result["toi_pp_per_game"] == pytest.approx(3.5)
        assert result["toi_sh_per_game"] == pytest.approx(0.2)

    def test_sh_pct_delta_computed_correctly(self) -> None:
        weighted = {}
        current = _make_row(sh_pct=0.125, sh_pct_career_avg=0.110)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["sh_pct_delta"] == pytest.approx(0.125 - 0.110)

    def test_sh_pct_delta_none_when_sh_pct_missing(self) -> None:
        weighted = {}
        current = _make_row(sh_pct=None, sh_pct_career_avg=0.110)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["sh_pct_delta"] is None

    def test_sh_pct_delta_none_when_career_avg_missing(self) -> None:
        weighted = {}
        current = _make_row(sh_pct=0.125, sh_pct_career_avg=None)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["sh_pct_delta"] is None

    def test_g_minus_ixg_passthrough(self) -> None:
        weighted = {}
        current = _make_row(g_minus_ixg=1.5)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["g_minus_ixg"] == pytest.approx(1.5)

    def test_g_per60_passthrough(self) -> None:
        weighted = {}
        current = _make_row(g_per60=2.8)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["g_per60"] == pytest.approx(2.8)

    def test_ixg_per60_curr_is_current_season(self) -> None:
        weighted = {"ixg_per60": 11.0}  # weighted avg — different from current
        current = _make_row(ixg_per60=13.5)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["ixg_per60_curr"] == pytest.approx(13.5)

    def test_age_computed_from_dob(self) -> None:
        # Season 2025 → Oct 1 2025; DoB 1997-01-13 → age 28
        weighted = {}
        current = _make_row(season=2025, date_of_birth="1997-01-13")
        result = _compute_aliases(weighted, current, prev=None)
        assert result["age"] == 28

    def test_age_birthday_after_oct1_rounds_down(self) -> None:
        # DoB 1997-11-01 — not yet 28 by Oct 1 2025
        weighted = {}
        current = _make_row(season=2025, date_of_birth="1997-11-01")
        result = _compute_aliases(weighted, current, prev=None)
        assert result["age"] == 27

    def test_icf_per60_delta_with_prev(self) -> None:
        weighted = {}
        current = _make_row(icf_per60=15.0)
        prev = _make_row(icf_per60=12.0)
        result = _compute_aliases(weighted, current, prev)
        assert result["icf_per60_delta"] == pytest.approx(3.0)

    def test_icf_per60_delta_none_without_prev(self) -> None:
        weighted = {}
        current = _make_row(icf_per60=15.0)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["icf_per60_delta"] is None

    def test_pp_unit_change_pp2_to_pp1(self) -> None:
        weighted = {}
        current = _make_row(pp_unit=1)
        prev = _make_row(pp_unit=2)
        result = _compute_aliases(weighted, current, prev)
        assert result["pp_unit_change"] == "PP2→PP1"

    def test_pp_unit_change_none_when_no_change(self) -> None:
        weighted = {}
        current = _make_row(pp_unit=1)
        prev = _make_row(pp_unit=1)
        result = _compute_aliases(weighted, current, prev)
        assert result["pp_unit_change"] is None

    def test_pp_unit_change_none_without_prev(self) -> None:
        weighted = {}
        current = _make_row(pp_unit=1)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["pp_unit_change"] is None

    def test_a2_pct_of_assists_always_none(self) -> None:
        weighted = {}
        current = _make_row()
        result = _compute_aliases(weighted, current, prev=None)
        assert result["a2_pct_of_assists"] is None
```

- [ ] **Step 2: Run — expect NotImplementedError**

```bash
pytest tests/services/test_feature_engineering.py::TestComputeAliases -v 2>&1 | head -10
```

- [ ] **Step 3: Implement `_compute_aliases` in `services/feature_engineering.py`**

Replace the `_compute_aliases` placeholder with:

```python
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
        sh_pct - sh_pct_career
        if sh_pct is not None and sh_pct_career is not None
        else None
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
            season_start.year - dob.year
            - ((season_start.month, season_start.day) < (dob.month, dob.day))
        )
    else:
        aliases["age"] = None

    # Delta features (require prior season)
    aliases["icf_per60_delta"] = (
        current["icf_per60"] - prev["icf_per60"]
        if prev is not None and current.get("icf_per60") is not None and prev.get("icf_per60") is not None
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
```

- [ ] **Step 4: Run alias tests — all must pass**

```bash
pytest tests/services/test_feature_engineering.py::TestComputeAliases -v
```
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add services/feature_engineering.py tests/services/test_feature_engineering.py
git commit -m "feat(3c): _compute_aliases — TOI rename, sh_pct_delta, age, delta features"
```

---

## Task 5: `_compute_breakout_signals`

**Files:** `services/feature_engineering.py`, `tests/services/test_feature_engineering.py`

- [ ] **Step 1: Add breakout signal tests**

```python
# Append to tests/services/test_feature_engineering.py

class TestComputeBreakoutSignals:
    """Each signal: test fires on boundary-meeting value, suppresses on boundary-missing value, suppresses on None."""

    def _features(self, **overrides: Any) -> dict:
        base = {
            "g_per60": 2.0,
            "ixg_per60_curr": 2.5,         # g_per60 < ixg * 0.85 → 2.0 < 2.125 → True
            "sh_pct_delta": -0.04,           # below_career → True
            "icf_per60_delta": 0.6,          # rising_shot_gen → True
            "pp_unit_change": "PP2→PP1",     # pp_promotion → True
            "age": 22,                       # prime_age_window → True
            "xgf_pct_5v5": 53.0,            # strong_underlying → True
            "pdo": 0.970,                    # bad_luck_pdo → True
            "elc_flag": True,
            "toi_ev_per_game": 15.0,         # elc_deployed → True
        }
        base.update(overrides)
        return base

    def test_g_below_ixg_fires(self) -> None:
        f = self._features(g_per60=2.0, ixg_per60_curr=2.5)  # 2.0 < 2.5*0.85=2.125
        assert _compute_breakout_signals(f)["g_below_ixg"] is True

    def test_g_below_ixg_suppressed(self) -> None:
        f = self._features(g_per60=2.5, ixg_per60_curr=2.5)  # 2.5 >= 2.125
        assert _compute_breakout_signals(f)["g_below_ixg"] is False

    def test_g_below_ixg_none_input(self) -> None:
        f = self._features(g_per60=None, ixg_per60_curr=2.5)
        assert _compute_breakout_signals(f)["g_below_ixg"] is False

    def test_sh_pct_below_career_fires(self) -> None:
        f = self._features(sh_pct_delta=-0.031)  # < -0.03
        assert _compute_breakout_signals(f)["sh_pct_below_career"] is True

    def test_sh_pct_below_career_suppressed(self) -> None:
        f = self._features(sh_pct_delta=-0.03)  # not < -0.03 (boundary)
        assert _compute_breakout_signals(f)["sh_pct_below_career"] is False

    def test_sh_pct_below_career_none(self) -> None:
        f = self._features(sh_pct_delta=None)
        assert _compute_breakout_signals(f)["sh_pct_below_career"] is False

    def test_rising_shot_gen_fires(self) -> None:
        f = self._features(icf_per60_delta=0.51)
        assert _compute_breakout_signals(f)["rising_shot_gen"] is True

    def test_rising_shot_gen_suppressed(self) -> None:
        f = self._features(icf_per60_delta=0.5)  # not > 0.5 (boundary)
        assert _compute_breakout_signals(f)["rising_shot_gen"] is False

    def test_rising_shot_gen_none(self) -> None:
        f = self._features(icf_per60_delta=None)
        assert _compute_breakout_signals(f)["rising_shot_gen"] is False

    def test_pp_promotion_fires(self) -> None:
        f = self._features(pp_unit_change="PP2→PP1")
        assert _compute_breakout_signals(f)["pp_promotion"] is True

    def test_pp_promotion_suppressed(self) -> None:
        f = self._features(pp_unit_change=None)
        assert _compute_breakout_signals(f)["pp_promotion"] is False

    def test_prime_age_window_fires_at_20(self) -> None:
        assert _compute_breakout_signals(self._features(age=20))["prime_age_window"] is True

    def test_prime_age_window_fires_at_25(self) -> None:
        assert _compute_breakout_signals(self._features(age=25))["prime_age_window"] is True

    def test_prime_age_window_suppressed_at_26(self) -> None:
        assert _compute_breakout_signals(self._features(age=26))["prime_age_window"] is False

    def test_prime_age_window_suppressed_at_19(self) -> None:
        # Lower bound: must be >= 20
        assert _compute_breakout_signals(self._features(age=19))["prime_age_window"] is False

    def test_prime_age_window_none(self) -> None:
        assert _compute_breakout_signals(self._features(age=None))["prime_age_window"] is False

    def test_strong_underlying_fires(self) -> None:
        assert _compute_breakout_signals(self._features(xgf_pct_5v5=52.1))["strong_underlying"] is True

    def test_strong_underlying_suppressed(self) -> None:
        assert _compute_breakout_signals(self._features(xgf_pct_5v5=52.0))["strong_underlying"] is False

    def test_strong_underlying_none(self) -> None:
        assert _compute_breakout_signals(self._features(xgf_pct_5v5=None))["strong_underlying"] is False

    def test_bad_luck_pdo_fires(self) -> None:
        assert _compute_breakout_signals(self._features(pdo=0.974))["bad_luck_pdo"] is True

    def test_bad_luck_pdo_suppressed(self) -> None:
        assert _compute_breakout_signals(self._features(pdo=0.975))["bad_luck_pdo"] is False

    def test_bad_luck_pdo_none(self) -> None:
        assert _compute_breakout_signals(self._features(pdo=None))["bad_luck_pdo"] is False

    def test_elc_deployed_fires(self) -> None:
        f = self._features(elc_flag=True, toi_ev_per_game=14.0)
        assert _compute_breakout_signals(f)["elc_deployed"] is True

    def test_elc_deployed_suppressed_low_toi(self) -> None:
        f = self._features(elc_flag=True, toi_ev_per_game=13.9)
        assert _compute_breakout_signals(f)["elc_deployed"] is False

    def test_elc_deployed_suppressed_not_elc(self) -> None:
        f = self._features(elc_flag=False, toi_ev_per_game=15.0)
        assert _compute_breakout_signals(f)["elc_deployed"] is False

    def test_elc_deployed_none_toi(self) -> None:
        f = self._features(elc_flag=True, toi_ev_per_game=None)
        assert _compute_breakout_signals(f)["elc_deployed"] is False

    def test_all_eight_signals_present_in_result(self) -> None:
        result = _compute_breakout_signals(self._features())
        expected_keys = {
            "g_below_ixg", "sh_pct_below_career", "rising_shot_gen",
            "pp_promotion", "prime_age_window", "strong_underlying",
            "bad_luck_pdo", "elc_deployed",
        }
        assert set(result.keys()) == expected_keys
```

- [ ] **Step 2: Run — expect NotImplementedError**

```bash
pytest tests/services/test_feature_engineering.py::TestComputeBreakoutSignals -v 2>&1 | head -5
```

- [ ] **Step 3: Implement `_compute_breakout_signals`**

Replace the placeholder with:

```python
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
        "g_below_ixg": (
            g_per60 is not None and ixg_curr is not None
            and g_per60 < ixg_curr * 0.85
        ),
        "sh_pct_below_career": sh_delta is not None and sh_delta < -0.03,
        "rising_shot_gen": icf_delta is not None and icf_delta > 0.5,
        "pp_promotion": features.get("pp_unit_change") == "PP2→PP1",
        "prime_age_window": age is not None and 20 <= age <= 25,
        "strong_underlying": xgf is not None and xgf > 52.0,
        "bad_luck_pdo": pdo is not None and pdo < 0.975,
        "elc_deployed": (
            _safe(elc) and toi_ev is not None and toi_ev >= 14.0
        ),
    }
```

- [ ] **Step 4: Run breakout tests — all must pass**

```bash
pytest tests/services/test_feature_engineering.py::TestComputeBreakoutSignals -v
```
Expected: 23 passed.

- [ ] **Step 5: Commit**

```bash
git add services/feature_engineering.py tests/services/test_feature_engineering.py
git commit -m "feat(3c): _compute_breakout_signals — all 8 rules with null safety"
```

---

## Task 6: `_compute_regression_signals`

**Files:** `services/feature_engineering.py`, `tests/services/test_feature_engineering.py`

- [ ] **Step 1: Add regression signal tests**

```python
# Append to tests/services/test_feature_engineering.py

class TestComputeRegressionSignals:

    def _features(self, **overrides: Any) -> dict:
        base = {
            "g_per60": 3.5,
            "ixg_per60_curr": 2.5,         # g > ixg * 1.20 → 3.5 > 3.0 → True
            "sh_pct_delta": 0.05,           # sh_pct_above_career → True
            "pdo": 1.030,                   # high_pdo → True
            "oi_sh_pct": 0.12,              # high_oi_sh_pct → True
            "a2_pct_of_assists": None,      # always None (D8)
            "age": 31,
            "position": "C",               # age_declining → True (NHL.com canonical: C/LW/RW, NOT "F")
            "icf_per60_delta": -0.6,        # declining_shot_gen → True
        }
        base.update(overrides)
        return base

    def test_g_above_ixg_fires(self) -> None:
        f = self._features(g_per60=3.5, ixg_per60_curr=2.5)  # 3.5 > 2.5*1.20=3.0
        assert _compute_regression_signals(f)["g_above_ixg"] is True

    def test_g_above_ixg_suppressed(self) -> None:
        f = self._features(g_per60=3.0, ixg_per60_curr=2.5)  # 3.0 == 3.0, not >
        assert _compute_regression_signals(f)["g_above_ixg"] is False

    def test_g_above_ixg_none_input(self) -> None:
        f = self._features(g_per60=None)
        assert _compute_regression_signals(f)["g_above_ixg"] is False

    def test_sh_pct_above_career_fires(self) -> None:
        f = self._features(sh_pct_delta=0.041)
        assert _compute_regression_signals(f)["sh_pct_above_career"] is True

    def test_sh_pct_above_career_suppressed(self) -> None:
        f = self._features(sh_pct_delta=0.04)  # not > 0.04
        assert _compute_regression_signals(f)["sh_pct_above_career"] is False

    def test_sh_pct_above_career_none(self) -> None:
        f = self._features(sh_pct_delta=None)
        assert _compute_regression_signals(f)["sh_pct_above_career"] is False

    def test_high_pdo_fires(self) -> None:
        f = self._features(pdo=1.026)
        assert _compute_regression_signals(f)["high_pdo"] is True

    def test_high_pdo_suppressed(self) -> None:
        f = self._features(pdo=1.025)  # not > 1.025
        assert _compute_regression_signals(f)["high_pdo"] is False

    def test_high_pdo_none(self) -> None:
        f = self._features(pdo=None)
        assert _compute_regression_signals(f)["high_pdo"] is False

    def test_high_oi_sh_pct_fires(self) -> None:
        f = self._features(oi_sh_pct=0.111)
        assert _compute_regression_signals(f)["high_oi_sh_pct"] is True

    def test_high_oi_sh_pct_suppressed(self) -> None:
        f = self._features(oi_sh_pct=0.11)  # not > 0.11
        assert _compute_regression_signals(f)["high_oi_sh_pct"] is False

    def test_high_oi_sh_pct_none(self) -> None:
        f = self._features(oi_sh_pct=None)
        assert _compute_regression_signals(f)["high_oi_sh_pct"] is False

    def test_high_secondary_pct_always_false(self) -> None:
        # D8: a1 counting stat not in schema; signal disabled in Phase 3c
        f = self._features(a2_pct_of_assists=None)
        assert _compute_regression_signals(f)["high_secondary_pct"] is False

    def test_age_declining_fires_forward_over_30(self) -> None:
        # DB stores NHL.com canonical positions: C, LW, RW for forwards — NOT "F"
        f = self._features(age=31, position="C")
        assert _compute_regression_signals(f)["age_declining"] is True

    def test_age_declining_fires_lw_and_rw(self) -> None:
        assert _compute_regression_signals(self._features(age=31, position="LW"))["age_declining"] is True
        assert _compute_regression_signals(self._features(age=31, position="RW"))["age_declining"] is True

    def test_age_declining_suppressed_at_30(self) -> None:
        f = self._features(age=30, position="C")  # not > 30
        assert _compute_regression_signals(f)["age_declining"] is False

    def test_age_declining_suppressed_for_defenseman(self) -> None:
        f = self._features(age=31, position="D")
        assert _compute_regression_signals(f)["age_declining"] is False

    def test_age_declining_suppressed_for_goalie(self) -> None:
        f = self._features(age=31, position="G")
        assert _compute_regression_signals(f)["age_declining"] is False

    def test_age_declining_none_age(self) -> None:
        f = self._features(age=None, position="C")
        assert _compute_regression_signals(f)["age_declining"] is False

    def test_declining_shot_gen_fires(self) -> None:
        f = self._features(icf_per60_delta=-0.51)
        assert _compute_regression_signals(f)["declining_shot_gen"] is True

    def test_declining_shot_gen_suppressed(self) -> None:
        f = self._features(icf_per60_delta=-0.5)  # not < -0.5
        assert _compute_regression_signals(f)["declining_shot_gen"] is False

    def test_declining_shot_gen_none(self) -> None:
        f = self._features(icf_per60_delta=None)
        assert _compute_regression_signals(f)["declining_shot_gen"] is False

    def test_all_seven_signals_present(self) -> None:
        result = _compute_regression_signals(self._features())
        expected_keys = {
            "g_above_ixg", "sh_pct_above_career", "high_pdo",
            "high_oi_sh_pct", "high_secondary_pct", "age_declining",
            "declining_shot_gen",
        }
        assert set(result.keys()) == expected_keys
```

- [ ] **Step 2: Run — expect NotImplementedError**

```bash
pytest tests/services/test_feature_engineering.py::TestComputeRegressionSignals -v 2>&1 | head -5
```

- [ ] **Step 3: Implement `_compute_regression_signals`**

```python
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
        "g_above_ixg": (
            g_per60 is not None and ixg_curr is not None
            and g_per60 > ixg_curr * 1.20
        ),
        "sh_pct_above_career": sh_delta is not None and sh_delta > 0.04,
        "high_pdo": pdo is not None and pdo > 1.025,
        "high_oi_sh_pct": oi_sh_pct is not None and oi_sh_pct > 0.11,
        # D8: primary_assists counting stat not in schema; disabled for Phase 3c
        "high_secondary_pct": False,
        # DB stores NHL.com canonical positions: C/LW/RW for forwards — NOT "F"
        "age_declining": age is not None and age > 30 and position in {"C", "LW", "RW"},
        "declining_shot_gen": icf_delta is not None and icf_delta < -0.5,
    }
```

- [ ] **Step 4: Run regression tests — all must pass**

```bash
pytest tests/services/test_feature_engineering.py::TestComputeRegressionSignals -v
```
Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
git add services/feature_engineering.py tests/services/test_feature_engineering.py
git commit -m "feat(3c): _compute_regression_signals — all 7 rules, high_secondary_pct disabled (D8)"
```

---

## Task 7: `_compute_projection_tier` + `build_feature_matrix`

**Files:** `services/feature_engineering.py`, `tests/services/test_feature_engineering.py`

- [ ] **Step 1: Add tier + round-trip tests**

```python
# Append to tests/services/test_feature_engineering.py

class TestComputeProjectionTier:
    def test_four_signals_high(self) -> None:
        assert _compute_projection_tier(4) == "HIGH"

    def test_five_signals_high(self) -> None:
        assert _compute_projection_tier(5) == "HIGH"

    def test_eight_signals_high(self) -> None:
        assert _compute_projection_tier(8) == "HIGH"

    def test_three_signals_medium(self) -> None:
        assert _compute_projection_tier(3) == "MEDIUM"

    def test_two_signals_low(self) -> None:
        assert _compute_projection_tier(2) == "LOW"

    def test_one_signal_none(self) -> None:
        assert _compute_projection_tier(1) is None

    def test_zero_signals_none(self) -> None:
        assert _compute_projection_tier(0) is None


class TestBuildFeatureMatrix:
    """Round-trip and integration tests for build_feature_matrix."""

    def _grouped(self, player_id: str = "p-mcdavid", seasons: int = 3) -> dict:
        rows = []
        for i in range(seasons):
            season = 2025 - i
            row = _make_row(
                season=season,
                toi_ev=21.0 - i,
                icf_per60=14.0 - i * 0.5,
                ixg_per60=12.0,
            )
            row["player_id"] = player_id
            rows.append(row)
        return {player_id: rows}

    def test_returns_list(self) -> None:
        result = build_feature_matrix(self._grouped())
        assert isinstance(result, list)

    def test_one_dict_per_player(self) -> None:
        grouped = {
            "p-mcdavid": self._grouped()["p-mcdavid"],
            "p-draisaitl": self._grouped("p-draisaitl")["p-draisaitl"],
        }
        result = build_feature_matrix(grouped)
        assert len(result) == 2

    def test_player_id_in_output(self) -> None:
        result = build_feature_matrix(self._grouped())
        assert result[0]["player_id"] == "p-mcdavid"

    def test_weighted_rate_stats_in_output(self) -> None:
        result = build_feature_matrix(self._grouped())
        for stat in _RATE_STATS:
            assert stat in result[0], f"Missing stat: {stat}"

    def test_breakout_tier_present(self) -> None:
        result = build_feature_matrix(self._grouped())
        assert "breakout_tier" in result[0]

    def test_regression_tier_present(self) -> None:
        result = build_feature_matrix(self._grouped())
        assert "regression_tier" in result[0]

    def test_breakout_signals_dict_in_output(self) -> None:
        result = build_feature_matrix(self._grouped())
        assert isinstance(result[0]["breakout_signals"], dict)
        assert len(result[0]["breakout_signals"]) == 8

    def test_regression_signals_dict_in_output(self) -> None:
        result = build_feature_matrix(self._grouped())
        assert isinstance(result[0]["regression_signals"], dict)
        assert len(result[0]["regression_signals"]) == 7

    def test_player_with_zero_qualifying_seasons_excluded(self) -> None:
        # toi_ev below threshold → excluded from output
        row = _make_row(season=2025, toi_ev=2.0)
        row["player_id"] = "p-healthy-scratch"
        result = build_feature_matrix({"p-healthy-scratch": [row]})
        assert result == []

    def test_both_tiers_independently_tracked(self) -> None:
        """breakout_tier and regression_tier are independent fields — both HIGH simultaneously is valid.

        Breakout: g_below_ixg, sh_pct_below_career, prime_age_window, bad_luck_pdo (4 → HIGH)
        Regression: sh_pct_above_career (False, contradicts breakout), high_oi_sh_pct,
                    high_secondary_pct (always False), declining_shot_gen, high_pdo (False).
        Use two separate players instead: one with 4 breakout, one with 4 regression.
        Then confirm each has the expected tier.
        """
        # 4 breakout signals: g_below_ixg + sh_pct_below_career + prime_age_window + bad_luck_pdo
        breakout_row = _make_row(
            season=2025,
            toi_ev=21.0,
            g_per60=1.5,
            ixg_per60=3.0,         # g(1.5) < ixg(3.0)*0.85=2.55 → g_below_ixg True
            sh_pct=0.06,
            sh_pct_career_avg=0.11,  # delta=-0.05 < -0.03 → sh_pct_below_career True
            pdo=0.960,               # bad_luck_pdo True
            date_of_birth="2003-01-01",  # age=22 → prime_age_window True
        )
        breakout_row["player_id"] = "p-breakout"

        # 4 regression signals: g_above_ixg + sh_pct_above_career + high_pdo + high_oi_sh_pct
        regression_row = _make_row(
            season=2025,
            toi_ev=21.0,
            g_per60=4.0,
            ixg_per60=3.0,           # g(4.0) > ixg(3.0)*1.20=3.6 → g_above_ixg True
            sh_pct=0.16,
            sh_pct_career_avg=0.11,  # delta=+0.05 > 0.04 → sh_pct_above_career True
            pdo=1.030,               # high_pdo True
            oi_sh_pct=0.12,          # high_oi_sh_pct True
            date_of_birth="1985-01-01",  # age=40 → age_declining suppressed (only C/LW/RW)
        )
        regression_row["player_id"] = "p-regression"

        grouped = {
            "p-breakout": [breakout_row],
            "p-regression": [regression_row],
        }
        result = {r["player_id"]: r for r in build_feature_matrix(grouped)}
        assert result["p-breakout"]["breakout_tier"] == "HIGH"
        assert result["p-regression"]["regression_tier"] == "HIGH"

    def test_all_required_keys_in_output(self) -> None:
        result = build_feature_matrix(self._grouped())
        player = result[0]
        required_keys = {
            "player_id", "season",
            # weighted rates
            "icf_per60", "ixg_per60", "xgf_pct_5v5", "cf_pct_adj",
            "scf_per60", "scf_pct", "p1_per60",
            "toi_ev_per_game", "toi_pp_per_game", "toi_sh_per_game",
            # current-season pass-throughs
            "g_per60", "ixg_per60_curr", "g_minus_ixg",
            "sh_pct_delta", "pdo", "pp_unit", "oi_sh_pct",
            "elc_flag", "contract_year_flag", "post_extension_flag",
            "age", "position",
            # deltas
            "icf_per60_delta", "pp_unit_change", "a2_pct_of_assists",
            # signals
            "breakout_signals", "regression_signals",
            "breakout_count", "regression_count",
            "breakout_tier", "regression_tier",
        }
        missing = required_keys - set(player.keys())
        assert not missing, f"Missing keys: {missing}"
```

- [ ] **Step 2: Run — expect NotImplementedError**

```bash
pytest tests/services/test_feature_engineering.py::TestComputeProjectionTier tests/services/test_feature_engineering.py::TestBuildFeatureMatrix -v 2>&1 | head -10
```

- [ ] **Step 3: Implement `_compute_projection_tier` and `build_feature_matrix`**

```python
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
) -> list[dict[str, Any]]:
    """Assemble the feature matrix from grouped player_stats rows.

    Args:
        grouped_stats: Output of PlayerStatsRepository.get_seasons_grouped().
                       {player_id: [current_row, y1_row, y2_row]} newest-first.

    Returns:
        List of feature dicts, one per player (excluding players with 0 qualifying
        seasons after TOI filter). Ordered by player_id ascending.
    """
    import logging

    logger = logging.getLogger(__name__)
    output: list[dict[str, Any]] = []

    for player_id in sorted(grouped_stats.keys()):
        rows = grouped_stats[player_id]
        if not rows:
            continue

        # Step 1: Weighted rates (TOI-filtered)
        weighted = _apply_weighted_rates(rows)
        qualifying_count = weighted.pop("_qualifying_count")

        if qualifying_count == 0:
            logger.warning("player %s excluded: 0 qualifying seasons after TOI filter", player_id)
            continue

        current = rows[0]
        prev = rows[1] if len(rows) > 1 else None

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
        output.append({
            "player_id": player_id,
            "season": current.get("season"),
            # Weighted rate features
            "icf_per60": weighted.get("icf_per60"),
            "ixg_per60": weighted.get("ixg_per60"),
            "xgf_pct_5v5": weighted.get("xgf_pct_5v5"),
            "cf_pct_adj": weighted.get("cf_pct_adj"),
            "scf_per60": weighted.get("scf_per60"),
            "scf_pct": weighted.get("scf_pct"),
            "p1_per60": weighted.get("p1_per60"),
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
        })

    return output
```

- [ ] **Step 4: Run full test suite — all must pass**

```bash
pytest tests/services/test_feature_engineering.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Run entire test suite**

```bash
pytest -v 2>&1 | tail -20
```
Expected: all existing tests still green.

- [ ] **Step 6: Commit**

```bash
git add services/feature_engineering.py tests/services/test_feature_engineering.py
git commit -m "feat(3c): build_feature_matrix + _compute_projection_tier — complete feature pipeline"
```

---

## Task 8: Finish + Review + PR

**Files:** all modified above

- [ ] **Step 1: Full lint + format**

```bash
cd apps/api
ruff check . && ruff format .
```
Fix any issues before proceeding.

- [ ] **Step 2: Full test suite — must be green**

```bash
pytest --tb=short 2>&1 | tail -30
```
Expected: 0 failed.

- [ ] **Step 3: Internal code review**
Use `superpowers:requesting-code-review` against the 4 new files.

- [ ] **Step 4: Update Notion card → In Review**
Update `[3c] feature_engineering.py` task card status.

- [ ] **Step 5: Commit + PR**
Use `commit-commands:commit-push-pr`. PR description must include:
- Summary of 4 new files
- Test count (run `pytest --collect-only -q | tail -5` for count)
- Design decisions referenced (D1–D8 from spec)
- Known limitations: `high_secondary_pct` disabled (D8), elite finisher exemption deferred (D5)

- [ ] **Step 6: External review (Tier 2 — Gemini + Codex)**

```bash
# From repo root
PR_DIFF=$(gh pr diff HEAD)

opencode run -m google/gemini-2.5-pro "$(cat .claude/feature-dev/prompts/plan-review-gemini.md)

$PR_DIFF"

opencode run -m openai/gpt-5.4 "$(cat .claude/feature-dev/prompts/plan-review-codex.md)

$PR_DIFF"
```

Triage findings at Final Review Gate before merging.

---

## Constants Cross-Reference

Both files must agree on these values:

| Constant | Value | Location |
|---|---|---|
| `PROJECTION_WINDOW` | `3` | `repositories/player_stats.py` + `services/feature_engineering.py` |
| `SEASON_WEIGHTS` | `[0.5, 0.3, 0.2]` | `services/feature_engineering.py` only |
| `TOI_THRESHOLD` | `5.0` | `services/feature_engineering.py` only |
| Breakout threshold | `>= 3 signals` | Signal count check in `build_feature_matrix` |
| Regression threshold | `>= 3 signals` | Signal count check in `build_feature_matrix` |

---

## Critical Naming Note

The feature dict contains **two `ixg_per60` values** with different semantics:

| Key | Semantics | Used by |
|---|---|---|
| `ixg_per60` | 3-year weighted average | Model training (Phase 3d) |
| `ixg_per60_curr` | Current-season raw value | Signal rules ONLY |

Signal rules (`_compute_breakout_signals`, `_compute_regression_signals`) **must always use `ixg_per60_curr`**. Using the weighted value would produce wrong results with no runtime error.
