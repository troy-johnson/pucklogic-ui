# Phase 3c — Feature Engineering Pipeline

**Date:** 2026-03-22
**Status:** Approved for implementation
**References:**
- `docs/specs/007-feature-engineering-spec.md` — feature definitions, signal rules, projection pipeline
- `docs/stats-research.md` — statistical methodology and source citations
- `docs/pucklogic-architecture.md` §6 — ML Trends Engine
- `supabase/migrations/003_phase3_ml_features.sql` — schema for all new columns
- `apps/api/CLAUDE.md` — Phase 3 status table

---

## Goals

Implement `services/feature_engineering.py` and `repositories/player_stats.py` — the feature matrix assembly pipeline that transforms raw `player_stats` rows into per-player feature dicts ready for model training (Phase 3d) and nightly inference (Phase 3e).

## Non-Goals

- XGBoost/LightGBM model training (Phase 3d)
- SHAP value computation (Phase 3d)
- `GET /trends` inference endpoint (Phase 3e)
- Layer 2 in-season Z-scores (v2.0)
- Goalie support (skaters only at launch)
- Pandas / numpy — plain Python dicts throughout; pandas introduced in Phase 3d training script

---

## Design Decisions

### D1 — Pure service + repository split
`services/feature_engineering.py` is a pure transform module (no DB dependency). `repositories/player_stats.py` handles all Supabase queries. Follows the established pattern in this codebase (`services/projections.py` + `repositories/projections.py`). Makes the service trivially testable with plain dicts — zero DB fixtures.

### D2 — Multi-season data via pre-grouped repository
The repository returns `Dict[str, List[dict]]` keyed by `player_id`, each value a list of season rows sorted newest-first (up to `window` seasons). The service receives organised data and applies weights — no grouping logic inside the service.

### D3 — 3-year weighted window for rate stats
Window = 3, weights = [0.5, 0.3, 0.2] (index 0 = most recent). Used for all rate stats (icf_per60, ixg_per60, xgf_pct_5v5, cf_pct_adj, scf_per60, scf_pct, p1_per60, toi_ev, toi_pp, toi_sh) and projected TOI.

**Rationale:** Industry standard validated by Luszczyszyn (GSVA), Evolving-Hockey (GAR/WAR), and TopDownHockey/JFresh — all independently use 3-year windows. Rooted in Tom Tango's Marcel system from MLB. Patrick Bacon's empirical testing on NHL data (2007–2025) consistently supports a 3-year window for skaters (single-year R² ≈ 0.35 to Year 2; multi-year substantially higher). The bias-variance tradeoff: 1 year = high variance; 4+ years = stale role/deployment data actively misleads; 3 years is the Goldilocks window. XGBoost (Evolving-Hockey) is trained on 2–3 years of prior data, directly validating this approach. Weights 0.5/0.3/0.2 sit between the Marcel 5/4/3 (42%/33%/25%) and 3/2/1 (50%/33%/17%) schemes — slightly more current-season emphasis than pure Marcel, within the validated range.

**Tunable constant:** `PROJECTION_WINDOW = 3` and `SEASON_WEIGHTS = [0.5, 0.3, 0.2]` are module-level constants, enabling future experimentation without code changes.

**Weight renormalization:** Players with fewer than 3 qualifying seasons have their available weights renormalized to sum to 1.0 (e.g., 2 seasons → [0.625, 0.375]). This is also the standard Marcel approach for limited data (rookies, shortened seasons).

### D4 — Same pipeline for training and inference
The feature service is shared by the Phase 3d training script and the Phase 3e nightly inference job. Using identical feature computation for both eliminates training/serving skew — a silent, hard-to-debug ML failure mode. The nightly job fetches 3 seasons × ~1000 active players = ~3000 rows, which is negligible.

### D5 — No elite finisher whitelist
The `g_above_ixg` regression signal fires for all players, including historically strong finishers. The XGBoost model (Phase 3d) learns the elite finisher pattern implicitly from training data — players with consistent multi-season `g > ixg` will have this reflected in their feature history. A hardcoded or manually-curated whitelist introduces human bias and is unnecessary in a trained model. Decision deferred to Phase 3d validation.

### D6 — Minimum TOI threshold applied pre-weighting
A season row is excluded from the **weighted rate average** if `toi_ev < 5.0` (equivalent to 300 ES minutes over ~60 games). Applied before weight renormalization so sparse seasons don't dilute the weighted result. Players with zero qualifying seasons after filtering are excluded from output and logged as a warning.

Note: `feature-engineering-spec.md` Training Data Requirements specifies 500 ES minutes as a minimum for the training dataset. These are two distinct thresholds: 300 min is the inference-time filter applied in this service (lenient — keeps players who missed games); 500 min is a stricter training-time filter applied in Phase 3d when building the labelled dataset (rejects noise from fringe players). Phase 3d must re-apply its own threshold independently when assembling training examples.

### D7 — Missing inputs default to False, never raise
Signal detection functions never raise on null inputs. A missing feature (None) causes the corresponding signal to evaluate to False. This is the conservative choice — omitting a signal is safer than inflating breakout/regression counts from data gaps.

### D8 — `a2_pct_of_assists` signal effectively disabled in Phase 3c
The `high_secondary_pct` regression signal requires `(primary_assists / total_assists)`. The initial schema (`001_initial_schema.sql`) has `a` (total assists) but no `a1` (primary assists counting stat). Phase 3a added `a1_per60` (a rate), which cannot be directly converted to a counting stat without introducing approximation error.

Rather than compute an approximate value, the signal defaults to False via D7 for all players in Phase 3c. This is the conservative choice. The XGBoost model (Phase 3d) can use `a1_per60` directly as a feature and learn the secondary assist pattern without the explicit signal rule. A future migration adding `a1` as a counting column would re-enable this signal. Threshold of 0.60 (from `feature-engineering-spec.md` §Regression Detection) is documented for when this is enabled.

---

## Architecture

### New Files

```
apps/api/
  repositories/
    player_stats.py              # NEW — multi-season query, grouped by player_id
  services/
    feature_engineering.py       # NEW — pure transforms: weighting, aliasing, signals
  tests/
    repositories/
      test_player_stats.py       # NEW
    services/
      test_feature_engineering.py  # NEW
```

### Interfaces

**`repositories/player_stats.py`**
```python
class PlayerStatsRepository:
    def get_seasons_grouped(
        self,
        season: int,
        window: int = PROJECTION_WINDOW,
    ) -> dict[str, list[dict]]:
        """
        Returns {player_id: [row_season_n, row_season_n1, row_season_n2]}
        sorted newest-first. Joins players table for date_of_birth and position.
        Players with fewer than `window` seasons return however many exist.
        """
```

**`services/feature_engineering.py`**
```python
PROJECTION_WINDOW: int = 3
SEASON_WEIGHTS: list[float] = [0.5, 0.3, 0.2]

def build_feature_matrix(
    grouped_stats: dict[str, list[dict]],
) -> list[dict]:
    """
    Pure transform. Returns one feature dict per player.
    Input: output of PlayerStatsRepository.get_seasons_grouped()
    Output: list of feature dicts with weighted rates, aliases, signals, tier
    """

# Private helpers (independently testable):
def _apply_weighted_rates(rows: list[dict]) -> dict: ...
def _compute_aliases(weighted: dict, current: dict, prev: dict | None) -> dict: ...
def _compute_breakout_signals(features: dict) -> dict[str, bool]: ...
def _compute_regression_signals(features: dict) -> dict[str, bool]: ...
def _compute_projection_tier(signal_count: int) -> str | None: ...
# Called twice: once for breakout_count, once for regression_count
```

---

## Data Flow

```
PlayerStatsRepository.get_seasons_grouped(season=2025, window=3)
  └─ Supabase: SELECT player_stats.*, players.date_of_birth, players.position
               WHERE season IN (2025, 2024, 2023)
               ORDER BY player_id, season DESC
     Returns: {"p-mcdavid": [2025_row, 2024_row, 2023_row], ...}

build_feature_matrix(grouped_stats)
  └─ For each player_id → rows:

     1. _apply_weighted_rates(rows)
        - Exclude rows where toi_ev < 5.0 (300-min threshold)
        - Renormalize SEASON_WEIGHTS for qualifying rows
        - Weighted avg: icf_per60, ixg_per60, xgf_pct_5v5, cf_pct_adj,
          scf_per60, scf_pct, p1_per60, toi_ev, toi_pp, toi_sh
        - Null stat in a row → excluded from that stat's weighted avg only
        - All rows null for a stat → feature is None

     NOTE on row references: `_apply_weighted_rates` uses the TOI-filtered subset of rows
     for weighted averages. `_compute_aliases` receives the **original unfiltered rows**
     (`rows[0]` = current season raw row, `rows[1]` = prior season raw row if present).
     If `rows[0]` fails the TOI threshold, the player has 0 qualifying rate stats (excluded
     from output per D6) — so aliases are only computed when at least rows[0] exists in
     the original list, regardless of TOI qualification.

     2. _compute_aliases(weighted, current_row=rows[0], prev_row=rows[1] or None)
        - toi_ev  → toi_ev_per_game  (from weighted rates)
        - toi_pp  → toi_pp_per_game  (from weighted rates)
        - toi_sh  → toi_sh_per_game  (from weighted rates)
        - sh_pct_delta    = current.sh_pct − current.sh_pct_career_avg  (None if either null)
        - g_minus_ixg     = current.g_minus_ixg  (pass-through; already stored)
        - g_per60         = current.g_per60  (pass-through; needed by breakout/regression signals)
        - ixg_per60_curr  = current.ixg_per60  (current-season, not weighted; needed by signals)
        - age             = years between players.date_of_birth and Oct 1 of season year
        - icf_per60_delta = current.icf_per60 − prev.icf_per60  (None if prev_row is None)
        - pp_unit_change  = "PP2→PP1" if current.pp_unit==1 and prev.pp_unit==2  (None if prev_row is None)
        - a2_pct_of_assists = None  (always — primary_assists counting stat not in schema; see D8)

     3. _compute_breakout_signals(features) → dict[str, bool]
        Evaluates all 8 rules from feature-engineering-spec.md §Breakout Detection.
        Signals use g_per60 and ixg_per60_curr (current-season, not weighted) per spec:
        g_below_ixg: g_per60 < ixg_per60_curr * 0.85
        sh_pct_below_career, rising_shot_gen, pp_promotion,
        prime_age_window, strong_underlying, bad_luck_pdo, elc_deployed

     4. _compute_regression_signals(features) → dict[str, bool]
        Evaluates all 7 rules from feature-engineering-spec.md §Regression Detection.
        g_above_ixg: g_per60 > ixg_per60_curr * 1.20  (current-season; no elite finisher exemption — D5)
        sh_pct_above_career, high_pdo, high_oi_sh_pct,
        high_secondary_pct, age_declining, declining_shot_gen

     5. Assemble final feature dict:
        {
          player_id, season,
          # weighted rate features
          icf_per60, ixg_per60, xgf_pct_5v5, cf_pct_adj,
          scf_per60, scf_pct, p1_per60,
          toi_ev_per_game, toi_pp_per_game, toi_sh_per_game,
          # current-season features (pass-through from rows[0])
          g_per60, ixg_per60_curr,   # used directly by signal rules
          g_minus_ixg, sh_pct_delta, pdo, pp_unit, oi_sh_pct,
          elc_flag, contract_year_flag, post_extension_flag,
          age, position,
          # delta features
          icf_per60_delta, pp_unit_change, a2_pct_of_assists,
          # signal outputs
          breakout_signals: dict[str, bool],
          regression_signals: dict[str, bool],
          breakout_count: int,
          regression_count: int,
          breakout_tier: "HIGH" | "MEDIUM" | "LOW" | None,
          regression_tier: "HIGH" | "MEDIUM" | "LOW" | None,
        }

     # NAMING NOTE FOR IMPLEMENTERS:
     # The feature dict contains TWO ixg_per60 values with different semantics:
     #   features["ixg_per60"]      = 3-year WEIGHTED AVERAGE (used as a model feature)
     #   features["ixg_per60_curr"] = CURRENT-SEASON raw value (used by signal rules only)
     # Signal rules (_compute_breakout_signals, _compute_regression_signals) MUST always
     # use ixg_per60_curr. Using ixg_per60 (weighted) in signals would produce wrong results
     # with no runtime error.

     projection_tier per category (HIGH = 4+, MEDIUM = 3, LOW = 2, None = <2):
       breakout_tier  = _compute_projection_tier(breakout_count)
       regression_tier = _compute_projection_tier(regression_count)

     The feature dict carries both tiers independently. How they map to the single
     player_trends.projection_tier column is resolved in Phase 3e (inference API).
     A player with simultaneous breakout + regression signals is valid — the model
     will learn what this pattern means from training data.
```

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Player has only 1 season | Weights renormalized to [1.0]; delta features set to None; signals requiring deltas → False |
| Season fails 300-min TOI threshold | Row excluded pre-weighting; remaining seasons renormalized |
| Player has 0 qualifying seasons | Excluded from output; logged as WARNING |
| Stat column is None in a row | Excluded from that stat's weighted avg only |
| All season rows null for a stat | Feature is None |
| Signal input is None | Signal evaluates to False — never raises |
| `sh_pct_career_avg` is None | `sh_pct_delta` → None; both SH% signals → False |
| `a2_pct_of_assists` | Always None — `a1` counting stat not in schema (see D8); `high_secondary_pct` → False for all players in Phase 3c |
| Tier 3 columns null for pre-3b seasons | `oi_sh_pct`, `speed_bursts_22`, `top_speed` etc. may be NULL for 2023/2024 rows scraped before Phase 3a migration. D7 (signal defaults to False on None) handles this gracefully — no special casing needed |

---

## Testing Plan

### `tests/repositories/test_player_stats.py`
- Returns correctly grouped and sorted dict for a 3-season query
- Players with 1 or 2 seasons return partial lists (no error)
- Joins `players` table for `date_of_birth` and `position`
- All tests use mocked Supabase client

### `tests/services/test_feature_engineering.py`
- Weighted average correct for 3, 2, and 1 qualifying seasons
- Weight renormalization correct when a season fails TOI threshold
- All 8 breakout signals fire and suppress on boundary values
- All 7 regression signals fire and suppress on boundary values
- None inputs never raise — signals default to False
- `sh_pct_delta` derivation correct; handles null `sh_pct_career_avg`
- `icf_per60_delta` and `pp_unit_change` correct with 2+ seasons; None with 1
- `a2_pct_of_assists` computed correctly; guards division-by-zero
- `projection_tier` correct at 4+, 3, 2, and <2 signal counts
- `_compute_projection_tier` in isolation: 0, 1, 2, 3, 4, 5 signal counts → correct tier; called separately for breakout and regression counts
- Both `breakout_tier` and `regression_tier` present in feature dict; a player with HIGH in both is valid
- Full round-trip: grouped input → feature dict with correct shape and all expected keys

All tests use constructed plain dicts — zero DB fixtures, zero Supabase mocks needed for the service layer.

---

## Risk & Scope

**Risk Tier:** 2 — Cross-module (new service + new repository, reads from DB, feeds Phase 3d training)
**Scope:** Medium (4 new files, ~350–450 lines total across service + repo + tests)
**Reviewer policy:** 1 external minimum

---

## Data Dependency

`player_stats` Tier 1 columns and the Phase 3c implementation are now in place. Phase 3b smoke coverage and subsequent Phase 3c implementation completed the core dependency chain for feature engineering. Current follow-up work is scraper hardening and historical backfill/data-quality verification on `feat/scraper-data-quality` (for example NHL.com aggregate/realtime correctness, NST parsing fixes, and Hockey Reference traded-player/career dedup). This is a reliability/data-quality pass for retraining and backfill confidence, not an unfinished Phase 3c implementation blocker.

---

## Out of Scope (Deferred)

| Item | Phase |
|---|---|
| Elite finisher whitelist / exemption logic | 3d — XGBoost learns pattern from training data |
| `post_extension_flag` signal usage | Included in feature dict (pass-through from player_stats); signal rule deferred — spec does not define a threshold rule for this flag, only a negative-signal context note |
| Aging curve adjustment multipliers | 3d — applied in training script |
| SH% regression toward career mean (step 2 of projection pipeline) | 3d |
| Projected TOI with context flag adjustments | 3d |
| Projected counting stats (rate × TOI) | 3d |
| Smoke test requiring live DB data | 3d+ — after scraper hardening/backfill verification run |
