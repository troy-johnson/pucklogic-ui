# Phase 3d — Model Training + Inference API

**Date:** 2026-03-23
**Status:** ✅ Complete — PR #28 open, all review issues resolved (commit 87a2d0a)
**Notion:** [3d] Model Training + Inference API — XGBoost/LightGBM, SHAP, GET /trends
**Estimated effort:** 20h across 2–3 sessions
**Risk tier:** 2 — Cross-module (new ML module, new Supabase Storage integration, writes to player_trends, new inference endpoint)
**Reviewer policy:** 1 external minimum (Gemini + Codex plan review)

---

## Implementation Notes (post-review deviations from original spec)

**GET /trends split out as Phase 3f (was D9 — merged into 3d):**
The inference endpoint is deferred. Phase 3e (new) = first real training run against
production Supabase. Phase 3f = inference API. `player_trends` must be non-empty before
3f makes sense. See SESSION_STATE.md checklist for the 3e gate.

**Holdout metrics: pre-retrain model evaluation (not final artifact):**
Original spec implied evaluating `final_model` on holdout. Fixed: `train_xgboost` and
`train_lightgbm` now train a `pre_retrain_model` on `X_train` only, evaluate it on
`X_holdout`, then retrain `final_model` on `X_all`. Reported metrics in `metadata.json`
are from `pre_retrain_model` — valid out-of-sample estimates.

**`--history` flag required in retrain workflow:**
`python -m scrapers.hockey_reference` with no flags only refreshes the current season.
`_main()` now accepts `--history` to call `scrape_history("2008-09", current_season)`.
`retrain-trends.yml` updated to use `--history` so multi-season training data is always
complete before `ml.train` runs.

**`.gitignore` path corrected:**
`.worktrees/` → `.claude/worktrees/` (the actual Claude worktree path).

---

## Architecture References

- `docs/pucklogic-architecture.md` § 6 (ML Trends Engine)
- `apps/api/CLAUDE.md` § Phase 3d
- `docs/feature-engineering-spec.md`
- Phase 3c spec: `docs/superpowers/specs/2026-03-22-phase3c-feature-engineering.md`

---

## Goals

1. Train XGBoost breakout and regression binary classifiers on historical `player_stats` data (2005–present).
2. Compute per-player SHAP values and upsert `player_trends` rows for the current season.
3. Serialize model artifacts to Supabase Storage (`ml-artifacts/<data_season>/`).
4. Load models at FastAPI startup; serve pre-computed scores via `GET /trends`.
5. Complete the GitHub Actions retraining workflow stub (`retrain-trends.yml`).

## Non-Goals

- Layer 2 in-season scoring (Z-scores, Celery nightly job) — v2.0
- Goalie model — Notion backlog (all scrapers are skater-only)
- MLflow experiment tracking — post-launch if needed
- Paywall gate on `GET /trends` — v2.0
- Real-time inference at request time — scores are pre-computed in `player_trends`
- LightGBM production artifact — challenger metrics only; XGBoost is the production model

---

## Design Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Flat `ml/` module: `train.py`, `loader.py`, `evaluate.py`, `shap_compute.py` | Matches Notion acceptance criteria; dataset (~5000 records) too small to need pipeline classes |
| D2 | DB-driven training data; `scrapers.hockey_reference scrape_history()` runs before training in GitHub Actions | Single source of truth; no static CSVs in git |
| D3 | Label metric: `p1_per60` from `player_stats` (primary points per 60 EV, populated by MoneyPuck/NST) | `a1` raw count is not a DB column; `p1_per60` is already in `_WEIGHTED_RATE_STATS` and is the equivalent rate stat |
| D4 | Training range starts 2005-06 (post-lockout rules change) | Pre-2005 data reflects a different game; 2005+ data is valid |
| D5 | Labeled training examples: ~2008–2024 (need 2 prior seasons for features + 1 future season for label) | 2005–2007 used only as lookback history |
| D6 | XGBoost handles feature NaN natively | Advanced stats (xG, NST) only available from ~2008–2010; no imputation needed |
| D7 | `breakout_count` / `regression_count` / tier fields excluded from model features | Signal summaries derived from the same features — would leak label-correlated information |
| D8 | Two independent binary classifiers: `breakout_model` and `regression_model` | A player can simultaneously show breakout and regression signals (rare but valid) |
| D9 | `GET /trends` deferred to Phase 3f (not in 3d) | Originally planned to merge into 3d. Post-implementation: `player_trends` must be verified non-empty via a real training run (Phase 3e) before the inference API is meaningful. Inference API moved to Phase 3f. |
| D10 | No caching on `GET /trends` in v1.0 | Scores update once per year; DB query is fast; avoids cache invalidation complexity |
| D11 | `pp_unit_change` excluded from model features | String value (`"PP2→PP1"` etc.) — XGBoost cannot ingest strings; `pp_unit` (current value) already captures PP assignment |
| D12 | `toi_ev_per_game` excluded from model features | Perfectly collinear with `toi_ev` (weighted average of per-game rate); including both inflates SHAP attribution |
| D13 | Label weights `[0.6, 0.4]` differ from feature weights `[0.5, 0.3, 0.2]` | Label measures realized production in a single future season — most recent prior season is a stronger predictor. Feature weights balance a longer history window. This is intentional and must not be unified. |
| D14 | `ModelNotAvailableError` defined in `ml/loader.py` | Keeps the exception co-located with the code that raises it; no shared exceptions module needed |
| D15 | 503 = Storage/load failure; `has_trends=False` = model never run for season | 503 is a deployment error (corrupted artifact, Storage unreachable). `has_trends=False` is a valid pre-training state. These are distinct and must not be conflated. |
| D16 | No persistent local cache in production (Railway/Fly.io ephemeral filesystem) | Dynos have no persistent disk; models download from Storage on every cold start into memory only. `~/.pucklogic/models/` cache is for local development only. |
| D17 | Artifact path derived from CLI `--season` arg: `--season 2026-27` → data season `2025-26` → `ml-artifacts/2025-26/` | Training season (future) ≠ data season (completed). Path always uses the completed data season. Derivation: `start = int(season.split("-")[0]); data_season = f"{start-1}-{str(start)[-2:]}"`. Input format must be `"YYYY-YY"`. Examples: `"2026-27"` → `"2025-26"`; `"2010-11"` → `"2009-10"`; `"2006-07"` → `"2005-06"`. Formula is valid for all seasons in the training range (2005–present). |

---

## Data Flow

```
retrain-trends.yml (GitHub Actions, Aug 1 annually + manual dispatch)
  │
  ├── scrapers.hockey_reference scrape_history()
  │     ensures historical player_stats exist in DB (2005–present)
  │     env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  │
  └── python -m ml.train --season 2026-27
        │   env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL
        │   data_season = derive_data_season("2026-27") = "2025-26"
        │   artifact_path = f"ml-artifacts/{data_season}/"
        │
        ├── PlayerStatsRepository.get_all_seasons_grouped()   [new method]
        │     returns {player_id: [all rows, newest-first]} — no season window cap
        │     columns: all columns from player_stats (same as get_seasons_grouped)
        │     joins players table for position, date_of_birth
        │
        ├── build_labeled_dataset(all_rows, train_seasons=range(2008, 2025))
        │     # Pseudocode (leakage guard explicit):
        │     #   for season N in train_seasons:
        │     #     feature_slice = {
        │     #       pid: [r for r in rows if r["season"] in (N, N-1, N-2)]
        │     #       for pid, rows in all_rows.items()
        │     #     }
        │     #     # Invariant: feature_slice NEVER contains rows where season == N+1
        │     #     assert all(r["season"] <= N for rows in feature_slice.values() for r in rows)
        │     #
        │     #     features = build_feature_matrix(feature_slice, season=N)
        │     #     # all_rows still contains N+1 rows — passed only to compute_label
        │     #
        │     #     for row in features:
        │     #       if row["stale_season"]: continue   # player absent in season N
        │     #       if row["position_type"] == "goalie": continue
        │     #       label = compute_label(row["player_id"], season_n=N, all_rows=all_rows)
        │     #       # compute_label uses all_rows[pid] with season == N+1 for label only
        │     #       if label is None: continue
        │     #       dataset.append((row, label))
        │     #
        │     # all_rows is passed to compute_label directly — never filtered to (N, N-1, N-2)
        │     # This is intentional: compute_label reads season N+1 from all_rows for the label target
        │
        ├── train_xgboost(X, y_breakout)   → breakout_model
        │     TimeSeriesSplit(n_splits=5, gap=0)
        │     holdout rows (2023–2024 seasons) excluded from ALL folds before split
        │     Optuna 50 trials → maximize mean AUC-ROC across folds
        │     Final model: retrain on ALL data 2008–2024 INCLUDING holdout seasons
        │       (holdout only excluded during CV; final retrain uses complete dataset)
        │     scale_pos_weight = n_neg / n_pos
        │
        ├── train_xgboost(X, y_regression) → regression_model
        │     (same hyperparameter space, independent Optuna study)
        │
        ├── train_lightgbm(X, y_breakout + y_regression)
        │     Optuna 25 trials each; is_unbalance=True
        │     Metrics logged to stdout + metadata.json only (no artifact upload)
        │     WARNING logged if LightGBM AUC-ROC > XGBoost by >0.02
        │
        ├── evaluate.py → final metrics on explicit holdout (2023–2024 seasons)
        │     holdout constructed BEFORE TimeSeriesSplit — never in any training fold
        │     metrics: AUC-ROC, precision@50, recall@50 per model
        │
        ├── shap_compute.py
        │     TreeExplainer(breakout_model).shap_values(X_current_season)
        │     top-3 by abs(shap_value) per player → ShapValues schema
        │     same for regression_model
        │
        ├── loader.upload(artifacts, data_season)
        │     → ml-artifacts/{data_season}/breakout_model.joblib
        │     → ml-artifacts/{data_season}/regression_model.joblib
        │     → ml-artifacts/{data_season}/metadata.json
        │     authenticates with SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
        │
        └── upsert player_trends (current-season skaters only)
              breakout_score, regression_risk, confidence,
              shap_values (JSONB), updated_at

FastAPI startup (lifespan in main.py)
  └── loader.load(settings.current_season)
        ├── derive data_season from current_season
        ├── download breakout_model.joblib + regression_model.joblib from Storage
        │   (no persistent local disk in production — download to memory on each cold start)
        │   (local dev: cache to ~/.pucklogic/models/<data_season>/ to skip re-download)
        ├── on Storage error or missing artifact: raise ModelNotAvailableError
        │   → caught by lifespan → app.state.models = None
        └── on success: app.state.models = (breakout_model, regression_model)

GET /trends?season=<season>
  ├── if app.state.models is None:
  │     → HTTP 503 {"detail": "Trends model not available for this season"}
  │     (indicates deployment error: artifact missing or Storage unreachable)
  └── TrendsRepository.get_trends(season)
        SELECT p.id, p.name, p.position, p.team,
               pt.breakout_score, pt.regression_risk, pt.confidence,
               pt.shap_values, pt.updated_at
        FROM players p
        LEFT JOIN player_trends pt ON p.id = pt.player_id AND pt.season = :season
        ORDER BY pt.breakout_score DESC NULLS LAST
  └── return TrendsResponse
        has_trends=False + updated_at=None if no player_trends rows found for season
        has_trends=True with full player list otherwise
```

---

## Label Computation

**Label metric:** `p1_per60` from `player_stats` (primary points per 60 EV, populated by MoneyPuck/NST scrapers). This is the same column used in `_WEIGHTED_RATE_STATS` in `feature_engineering.py`.

**Label weights** `[0.6, 0.4]` differ intentionally from feature weights `[0.5, 0.3, 0.2]` — see D13.

```python
def compute_label(
    player_id: str,
    season_n: int,
    all_rows: dict[str, list[dict]],
) -> tuple[int, int] | None:
    """Returns (breakout_label, regression_label) or None if insufficient data.

    Uses p1_per60 from player_stats directly (primary points per 60 EV).
    Label weights [0.6, 0.4] are intentionally different from feature weights
    [0.5, 0.3, 0.2] — see spec D13.
    """
    rows = all_rows.get(player_id, [])

    # Future season (label target) — never exposed to build_feature_matrix
    curr_row = next((r for r in rows if r["season"] == season_n + 1), None)

    # Prior seasons (trailing average baseline)
    prev_rows = [r for r in rows if r["season"] in (season_n, season_n - 1)]

    # MIN_TOI = 5.0 min/game — matches TOI_THRESHOLD in feature_engineering.py.
    # toi_ev is stored as a per-game rate (NST: total_toi / gp), so compare directly.
    # This filter is standalone in train.py and independent of build_feature_matrix's
    # TOI_THRESHOLD — both use 5.0 min/game but serve different purposes (label vs features).
    MIN_TOI = 5.0  # min/game, matches TOI_THRESHOLD in feature_engineering.py

    if curr_row is None or (curr_row.get("toi_ev") or 0) < MIN_TOI:
        return None
    if not prev_rows:
        return None

    curr_p60 = curr_row.get("p1_per60")  # rate stat from DB — no reconstruction needed
    prev_p60_values = [
        r.get("p1_per60")
        for r in prev_rows
        if r.get("p1_per60") is not None and (r.get("toi_ev") or 0) >= MIN_TOI
    ]

    if curr_p60 is None or not prev_p60_values:
        return None

    # Weighted average: 0.6 most recent, 0.4 prior (renormalized if only one season)
    weights = [0.6, 0.4][: len(prev_p60_values)]
    total_w = sum(weights)
    avg_p60 = sum(w * v for w, v in zip(weights, prev_p60_values)) / total_w

    if avg_p60 < 1e-6:  # guard against division by near-zero
        return None

    delta = (curr_p60 - avg_p60) / avg_p60
    return (1 if delta >= 0.20 else 0), (1 if delta <= -0.20 else 0)
```

---

## Module Layout

```
apps/api/
  ml/
    __init__.py
    train.py            # CLI: python -m ml.train --season 2026-27
    loader.py           # load() + upload(); ModelNotAvailableError defined here
    evaluate.py         # compute_metrics(y_true, y_pred_proba) → MetricsResult
    shap_compute.py     # compute_shap(model, X, feature_names) → list[ShapValues]
  repositories/
    trends.py           # TrendsRepository.get_trends(season) → list[dict]
  routers/
    trends.py           # GET /trends
  tests/
    ml/
      __init__.py
      test_train.py       # label computation, filtering, class weights, leakage guard
      test_evaluate.py    # AUC-ROC / precision@50 / recall@50 with known predictions
      test_loader.py      # ModelNotAvailableError on missing artifact, dev cache hit
      test_shap_compute.py  # top-3 extraction, output shape matches player count
    smoke/
      test_train_smoke.py   # 50-player synthetic → artifacts created + player_trends upserted
    repositories/
      test_trends.py    # LEFT JOIN null handling, ordering by breakout_score
    routers/
      test_trends.py    # TrendsResponse shape; 503 when app.state.models=None
```

---

## New Repository Method

**`PlayerStatsRepository.get_all_seasons_grouped()`**

- Returns `dict[str, list[dict]]` — `{player_id: [rows newest-first]}` with **no season-window cap**
- Column contract: identical to `get_seasons_grouped()` (same `player_stats` columns + `players` join for `position`, `date_of_birth`)
- Must include: `p1_per60`, `toi_ev`, `season`, `position` — required for label computation and `build_feature_matrix`
- **Join type:** LEFT JOIN on `players` table — preserves players who have `player_stats` rows but no `players` record (debutants or late-registered). For such rows, `position` and `date_of_birth` will be `None`. These rows are filtered out at training time: `position_type="goalie"` filter drops nulls, and `age=None` in `build_feature_matrix` causes those rows to produce `None` for age (signal rules handle this gracefully).
- **Relation to `get_seasons_grouped()`:** This is a new method; it does NOT call the existing `get_seasons_grouped(season, window=3)`. The existing method is capped to a 3-season window and requires a specific season. `get_all_seasons_grouped()` returns all historical rows for all players with no window cap, used only for training.
- Used only by `ml/train.py`; `get_seasons_grouped()` remains unchanged for inference

---

## Artifact Storage

**Supabase Storage bucket:** `ml-artifacts` (private — service role only).

**Prerequisite:** Create bucket manually in Supabase dashboard before first training run.
Add to `retrain-trends.yml` comments and project README.

**Season convention:**
- CLI arg `--season 2026-27` = the upcoming draft season (training target)
- Data season = `2025-26` (the completed season used for training data)
- Artifact path always uses data season: `ml-artifacts/2025-26/`

```
ml-artifacts/
  {data_season}/
    breakout_model.joblib
    regression_model.joblib
    metadata.json
```

**`metadata.json` shape:**
```json
{
  "season": "2025-26",
  "trained_at": "2026-08-01T08:32:00Z",
  "n_train": 4821,
  "n_holdout": 412,
  "feature_names": ["icf_per60", "ixg_per60", "..."],  // 21 features
  "breakout": { "auc_roc": 0.74, "precision_at_50": 0.62, "recall_at_50": 0.41 },
  "regression": { "auc_roc": 0.71, "precision_at_50": 0.58, "recall_at_50": 0.38 },
  "lgb_breakout_auc_roc": 0.73,
  "lgb_regression_auc_roc": 0.70
}
```

---

## Model Features

**21 columns** selected from `build_feature_matrix` output (numeric only):

`icf_per60`, `ixg_per60`, `xgf_pct_5v5`, `cf_pct_adj`, `scf_per60`, `scf_pct`,
`p1_per60`, `toi_ev`, `toi_pp`, `g_per60`, `ixg_per60_curr`, `g_minus_ixg`,
`sh_pct_delta`, `pdo`, `pp_unit`, `oi_sh_pct`, `elc_flag`, `contract_year_flag`,
`post_extension_flag`, `age`, `icf_per60_delta`

**`toi_ev` vs `toi_ev_per_game` — alias clarification (B1):**
`build_feature_matrix` emits both `toi_ev` and `toi_ev_per_game`. They hold the same value
(NST stores `total_toi / gp`, so `toi_ev` is already a per-game rate). The model receives
the column **named `toi_ev`**. The column named `toi_ev_per_game` is dropped before fitting
(see D12). Code must select features by name from the feature matrix dict, not by position.

**Excluded from model input:**
- `toi_ev_per_game` — alias for `toi_ev`; identical values, including both inflates SHAP attribution (D12)
- `toi_pp_per_game`, `toi_sh_per_game` — aliases for `toi_pp` / `toi_sh` respectively; same values as the weighted rate columns, excluded for the same collinearity reason as `toi_ev_per_game` (D12)
- `pp_unit_change` — string value (`"PP2→PP1"`), XGBoost cannot ingest strings (D11)
- `a2_pct_of_assists` — always None (Phase 3c D8)
- `breakout_count`, `regression_count`, `breakout_tier`, `regression_tier` — signal summaries; would leak label-correlated information (D7)
- `player_id`, `season`, `stale_season`, `position_type`, `position` — metadata/eligibility, not features
- `toi_sh` — shorthanded TOI; not predictive for offensive breakout/regression at the feature granularity of this model; excluded to reduce noise
- `breakout_signals`, `regression_signals` — dict output; not a scalar feature
- `scf_per60_curr` — not a field emitted by build_feature_matrix

---

## Inference API

**`GET /trends?season=<season>`**

- No auth required (v1.0 — all scores public)
- `season` defaults to `settings.current_season` if omitted
- Returns `TrendsResponse` (schema defined in Phase 3a, `models/schemas.py`)
- Players with no `player_trends` row: included with null scores (LEFT JOIN) — never 500
- `has_trends=False` + `updated_at=None` if no rows exist for season (valid pre-training state)
- HTTP 503 only when `app.state.models is None` (Storage error or corrupted artifact at startup)
- **503 vs `has_trends=False`:** 503 = deployment error. `has_trends=False` = model not yet run for this season. These are distinct — do not conflate.

---

## GitHub Actions — `retrain-trends.yml` (completed)

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with: { python-version: "3.11", cache: pip }
  - name: Install dependencies
    run: pip install -e ".[dev]"

  - name: Run Hockey Reference scraper (career SH%, history)
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
    run: python -m scrapers.hockey_reference

  - name: Train Trends model
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
      DATABASE_URL: ${{ secrets.DATABASE_URL }}
    run: python -m ml.train --season ${{ vars.CURRENT_SEASON }}
    # CURRENT_SEASON is a GitHub Actions variable (not secret), e.g. "2026-27"
    # ml-artifacts bucket must exist in Supabase Storage before this runs
```

**Required secrets:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`
**Required variable:** `CURRENT_SEASON` (GitHub Actions variable, e.g. `2026-27`)

---

## Acceptance Criteria

### Training pipeline
- [ ] `python -m ml.train --season 2026-27` completes without error on a machine with DB access
- [ ] Artifact path derived from CLI arg: `--season 2026-27` → `ml-artifacts/2025-26/`
- [ ] Both model artifacts uploaded to `ml-artifacts/2025-26/` in Supabase Storage
- [ ] `metadata.json` contains AUC-ROC, precision@50, recall@50 for both models
- [ ] `player_trends` rows upserted for all current-season skaters with qualifying TOI
- [ ] LightGBM challenger metrics logged; WARNING emitted if LightGBM beats XGBoost by >0.02
- [ ] `stale_season=True` and `position_type="goalie"` rows excluded from training set
- [ ] Feature window for season N contains only rows for N, N-1, N-2 (N+1 never in features)
- [ ] Holdout set (2023–2024) excluded from all TimeSeriesSplit folds before CV begins
- [ ] Final model retrains on ALL rows 2008–2024 INCLUDING holdout seasons (holdout exclusion is CV-only)

### Loader
- [ ] FastAPI starts without error when model artifact exists in Storage
- [ ] FastAPI starts without error when artifact missing (`app.state.models = None`, no crash)
- [ ] `ModelNotAvailableError` raised on Storage error or missing file
- [ ] Development: local cache at `~/.pucklogic/models/<data_season>/` skips re-download
- [ ] Production: no persistent local cache assumed (download on each cold start)

### Inference API
- [ ] `GET /trends?season=2026-27` returns `TrendsResponse` with correct shape
- [ ] Players with no `player_trends` row return null scores, not 500
- [ ] `GET /trends` returns HTTP 503 when `app.state.models is None` (deployment error only)
- [ ] `GET /trends` returns `has_trends=False` when model never run for season (not 503)
- [ ] `routers/trends.py` registered in `main.py`

### Tests
- [ ] All new tests pass (`pytest`)
- [ ] `test_train.py`: label leakage guard — assert season N+1 rows absent from feature slice
- [ ] Smoke test: 50-player synthetic dataset → model artifacts created + `player_trends` upserted
- [ ] CI: pre-serialized fixture model used; no real training in CI

### GitHub Actions
- [ ] `retrain-trends.yml` complete with scraper + training steps
- [ ] Required secrets documented: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`
- [ ] Required variable documented: `CURRENT_SEASON` (GitHub Actions variable)
- [ ] `ml-artifacts` Supabase Storage bucket creation documented in workflow comments

### Dependencies
- [ ] `xgboost`, `lightgbm`, `shap`, `optuna`, `scikit-learn` added to `pyproject.toml`

---

## Open Questions (resolved)

All resolved during brainstorming. No blocking questions remain.
