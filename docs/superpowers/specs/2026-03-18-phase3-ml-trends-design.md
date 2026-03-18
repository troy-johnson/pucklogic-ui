# Phase 3 — ML Trends Engine: Design Spec

**Date:** 2026-03-18
**Status:** Approved
**Scope:** v1.0 Layer 1 only (pre-season breakout/regression scores)
**Layer 2** (in-season Z-scores, Celery, combined PuckLogic Trends Score) is explicitly deferred to v2.0.

---

## Overview

Phase 3 builds the ML Trends Engine that overlays breakout/regression scores on top of the Phase 2 rankings dashboard. It is divided into five sequential milestones:

| Milestone | Name | Goal |
|-----------|------|------|
| **3a** | Scrapers & Data Pipeline | All data sources ingested, scrapers verified green |
| **3b** | Feature Engineering | Cleaned, normalized feature matrix per player per season |
| **3c** | Model Training | XGBoost/LightGBM breakout + regression models, SHAP values |
| **3d** | Inference API | `GET /trends` endpoint serving pre-computed scores |
| **3e** | Retraining Workflow | GitHub Actions yearly retraining trigger |

Each milestone ships independently and has its own test coverage before the next begins.

---

## Milestone 3a — Scrapers & Full Data Pipeline

### Goal

All data sources that feed the Layer 1 model are actively ingesting into Supabase. Every scraper has been run end-to-end and verified against real data. Historical data (10+ seasons where needed) is loaded.

### Problem

The existing NHL.com and MoneyPuck scrapers have never run successfully in production — the database has no real stat data. All Phase 3 feature engineering and model training depends on this data existing first.

### Data Sources Required

#### Already Have Scrapers (Verify & Fix)

| Source | Table | Frequency | Status |
|--------|-------|-----------|--------|
| NHL.com | `player_stats` | Daily | Scraper exists, never run successfully |
| MoneyPuck | `player_stats` | Daily | Scraper exists, never run successfully |
| Natural Stat Trick | `player_stats` | Daily | Scraper exists, unverified |
| DailyFaceoff | `player_projections` | Daily (season window) | PP unit data needed for `pp_unit` feature; daily updates required for in-season trending (Layer 2). Run daily from ~3 days before Opening Night through end of regular season. GitHub Actions cron: `0 8 * * *` with season-window guard. |

#### New Scrapers Required

| Source | Table | Data Needed | Cost |
|--------|-------|-------------|------|
| Hockey Reference | `player_stats_history` or `player_stats` extended | Career SH%, 10+ season history for `sh_pct_delta` and `age` features | Free |
| Elite Prospects | `player_metadata` or flag columns | ELC flag, contract year, entry-level status for Tier 3 features | Free (rate-limited) |
| Evolving Hockey | `player_stats` extended | GAR, xGAR (Tier 2) | $5/mo subscription; updated periodically (see note below) |
| NHL EDGE | `player_stats` extended | Speed bursts ≥22mph, top speed (Tier 3, optional) | Free via NHL API |

#### Non-Public / Paywalled Sources (Manual Ingestion via Custom Upload)

These sources are ingested manually each season using the existing `POST /sources/upload` endpoint. They serve three purposes:

1. **Personal aggregation** — available as weighted sources in your own rankings immediately on upload
2. **Future public aggregation** — if licensing is obtained, these can be promoted to system sources available to all users (no code changes needed — just flip `user_id = NULL` on the source row and `is_paid` as appropriate)
3. **Model validation / spot-checking** — cross-referencing model breakout picks against expert projections helps surface outliers and calibration issues

| Source | Ingestion cadence | Notes |
|--------|-------------------|-------|
| Dom Luszczyszyn (Evolving Hockey) | Pre-season, once per season | GAR-weighted projections; also useful as a training label sanity check |
| Dobber Hockey | Pre-season, once per season | Fantasy-point projections; strong baseline for spot-checking outliers |
| Apples & Ginos | Pre-season, once per season | Widely cited community projections |

No automated scraper — these are paywalled/licensed and must be uploaded manually. The custom upload endpoint handles column mapping and player matching.

**Evolving Hockey update cadence note:** GAR/xGAR are cumulative season statistics. They need to be refreshed:
- **Pre-season:** pull prior full season's final values for Layer 1 model training (once per year, ~June)
- **In-season (v2.0):** pull weekly or biweekly for Layer 2 Z-score features
- For v1.0, a single annual pull at pre-season model retraining time is sufficient. Cancel the $5/mo subscription after each pull if not needed in-season.

### Schema Changes

**`player_stats` — add columns if missing:**
```sql
-- Advanced stats from NST/MoneyPuck (may already exist)
ixg_per60          float,
xgf_pct_5v5        float,
scf_per60          float,
scf_pct            float,
cf_pct_adj         float,
cf_pct_rel         float,
g_minus_ixg        float,

-- From Evolving Hockey (one-time pull)
gar                float,
xgar               float,

-- Career/historical from Hockey Reference
sh_pct_career_avg  float,   -- rolling career SH% (not single season)

-- NHL EDGE (optional, Tier 3)
speed_bursts_22    float,
top_speed          float
```

**Flag columns — add to `player_stats` (not a separate table):**

`docs/feature-engineering-spec.md` specifies these as `ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS ...` statements. This spec supersedes the earlier idea of a separate `player_metadata` table. Keeping flags in `player_stats` avoids an extra JOIN in the feature matrix query and is consistent with the existing schema pattern (one row per player per season).

```sql
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS elc_flag boolean DEFAULT false;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS contract_year_flag boolean DEFAULT false;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS post_extension_flag boolean DEFAULT false;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS coaching_change_flag boolean DEFAULT false;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS trade_flag boolean DEFAULT false;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS nhl_experience int;
```

### Scraper Verification Criteria

A scraper is considered "verified" when:
1. Runs end-to-end without error on a real GitHub Actions cron trigger
2. At least one full season of data is present in the target table
3. Player name matching rate ≥ 95% (checked via `PlayerMatcher` match log)
4. Unit tests pass (`pytest tests/scrapers/`)

### Testing

- Each scraper gets a `tests/scrapers/test_<name>.py` with mocked HTTP responses
- Integration test: seed known player rows, run scraper in test mode, assert stat rows created
- Historical ingestion: CSV fixture test for Hockey Reference multi-season parsing

---

## Milestone 3b — Feature Engineering

### Goal

A reproducible pipeline that reads raw stats from Supabase and produces a normalized feature matrix (one row per player per season) ready for model training.

### Architecture

```
apps/api/scrapers/features/
  __init__.py          # public API: build_feature_matrix(season) → pd.DataFrame
  raw.py               # fetch player_stats from Supabase (flags are columns in player_stats)
  transforms.py        # compute derived features (sh_pct_delta, toi_rank, etc.)
  labels.py            # compute breakout/regression labels from historical data
  validation.py        # assert schema, check for nulls, log coverage %
```

### Feature Set (from `docs/feature-engineering-spec.md`)

#### Tier 1 — Core (Always Include)

| Feature | Source |
|---------|--------|
| `icf_per60` | NST |
| `ixg_per60` | MoneyPuck, NST |
| `g_minus_ixg` | MoneyPuck, NST |
| `xgf_pct_5v5` | MoneyPuck, NST |
| `cf_pct_adj` | NST |
| `scf_per60` | NST |
| `scf_pct` | NST |
| `p1_per60` | NST |
| `toi_ev_per_game` | All |
| `toi_pp_per_game` | All |
| `toi_sh_per_game` | All |
| `pp_unit` | DailyFaceoff |
| `pdo` | NST |
| `sh_pct_delta` | Hockey Reference (career avg) |
| `age` | Hockey Reference |

#### Tier 2 — Supplementary (Include with Caveats)

`cf_pct_rel`, `gar`/`xgar`, `xga_per60`, `g_per60`, `a1_per60`, `ppp_per60`, `toi_rank`, `qot_score`, `nhl_experience`, `position_code`, `fo_pct`, `zone_entry_rate`

#### Tier 3 — Situational (Use Carefully)

`speed_bursts_22`, `top_speed`, `ozs_pct`, `hits_per60`, `blocks_per60`, `pim_per60`, `oi_sh_pct`, `contract_year_flag`, `post_extension_flag`, `elc_flag`, `coaching_change_flag`, `trade_flag`

#### Tier 4 — Exclude

Raw GF%, SAT for counts (use rates), `ga60` for goalie proxy, raw PDO (use delta form).

### Label Definition

**Minimum inclusion threshold:** 500 even-strength minutes per season (per `docs/feature-engineering-spec.md`). Players below this threshold are excluded from the training set.

**Rate definition:** Rate = events per 60 min at even strength (not per game). The 3-year weighted average from `feature-engineering-spec.md §Projection Pipeline` is used: current season × 0.5, Y-1 × 0.3, Y-2 × 0.2.

**Single prior season:** If only one prior season is available (rookie, injury year), fall back to that single season's rate with a flat weight of 1.0. Players with zero prior NHL seasons are excluded from the label set (include in inference only).

- **Breakout:** actual-season fantasy points per 60 ≥ 20% above weighted trailing-season average, subject to ≥ 500 ES minutes in the label season and ≥ 500 ES minutes in each prior season used
- **Regression:** actual-season fantasy points per 60 ≤ 20% below weighted trailing-season average, same threshold
- **Neither:** all other qualifying players (majority class)

Labels are mutually exclusive by construction (a player cannot be both ≥20% above and ≤20% below the same baseline). Label type: binary per target — `is_breakout` (1/0) and `is_regression` (1/0). Two separate binary classifiers.

**Note on `feature-engineering-spec.md` signal rules:** That document defines rule-based breakout/regression signal detection (3+ signals = flag) used in the projection pipeline. The ML labels above are the ground-truth outcome labels for model training — they measure whether the player actually broke out/regressed, not whether they were flagged. The two definitions are complementary, not conflicting.

### Missing Data Strategy

- Tier 1 features with >30% nulls → log warning, impute with position-group median
- Tier 1 features with >60% nulls → drop that season from training set
- Tier 2/3 features: drop column if null rate > 40%
- Never impute labels — drop rows with missing labels

### Testing

- `test_build_feature_matrix`: runs against a seeded test DB, checks output shape and column presence
- `test_labels`: known player + known historical stats → assert correct label
- `test_validation`: feed bad data, assert ValidationError raised
- Coverage target: ≥ 85% on `features/` module

---

## Milestone 3c — Model Training

### Goal

Train XGBoost breakout and regression models on historical feature matrix. Serialize to joblib. Pre-compute SHAP values. Store scores in `player_trends`.

### Architecture

```
apps/api/ml/
  __init__.py
  train.py             # train() → uploads artifacts to Supabase Storage (primary store)
  loader.py            # load_model_artifacts(season) → downloads from Supabase Storage to disk cache
  evaluate.py          # cross-validation, AUC-ROC, precision@K
  shap_compute.py      # compute SHAP values for each player in current season
  artifacts/           # gitignored — local disk cache only; populated by loader.py at startup
    breakout_model.joblib
    regression_model.joblib
    feature_columns.json   # ordered list for inference consistency
```

**Artifact flow:** `train.py` serializes and uploads to Supabase Storage bucket `ml-artifacts/<season>/`. On FastAPI startup, `loader.py` checks if the local cache is populated; if not, downloads from storage. Local cache persists for the lifetime of the Railway dyno.

### Model Spec

- **Algorithm:** XGBoost (primary); LightGBM as challenger
- **Validation:** 5-fold time-series cross-validation (never train on future seasons)
- **Class imbalance:** `scale_pos_weight` in XGBoost (breakout base rate ~15–20%)
- **Hyperparameter tuning:** Optuna with 50 trials, optimize AUC-ROC
- **Evaluation metrics:** AUC-ROC, precision@50 (top 50 players), recall@50

### SHAP

- Use `shap.TreeExplainer` (fast for tree models, <1ms per player)
- Compute SHAP values for every player in the current season's feature matrix
- Store as JSONB in `player_trends.shap_values`:

```json
{
  "breakout": {
    "g_minus_ixg": 0.18,
    "pp_unit": 0.12,
    "sh_pct_delta": -0.09,
    ...
  },
  "regression": { ... }
}
```

### Output — `player_trends` table

```sql
-- Already exists; confirm these columns are present:
breakout_score    float,   -- 0.0–1.0 probability
regression_risk   float,   -- 0.0–1.0 probability
confidence        float,   -- model confidence (max class probability)
shap_values       jsonb,   -- per-feature contributions
updated_at        timestamptz,
season            text,
PRIMARY KEY / UNIQUE (player_id, season)
```

### Training Script Invocation

```bash
# from apps/api/
python -m ml.train --season 2024-25 --output ml/artifacts/
```

### Testing

- `test_train_smoke`: runs training on a 50-player synthetic dataset, asserts model artifact created
- `test_shap_compute`: synthetic features → SHAP output shape and sign sanity checks
- `test_evaluate`: known prediction set → AUC-ROC ≥ 0.5 (better than random)
- No real model training in CI — use pre-serialized fixture model

---

## Milestone 3d — Inference API

### Goal

`GET /trends` endpoint that returns pre-computed Layer 1 scores for all players for a given season. No paywall gate in v1.0 (all scores visible to free users).

### Endpoint

```
GET /trends?season=2024-25
Authorization: Bearer <token>  (optional in v1.0 — no gate)

Response: TrendsResponse
  {
    season: str,
    updated_at: str,
    players: [
      {
        player_id: str,
        name: str,
        position: str,
        team: str,
        breakout_score: float | null,
        regression_risk: float | null,
        confidence: float | null,
        shap_values: {
          breakout: { [feature: str]: float },
          regression: { [feature: str]: float }
        } | null
      }
    ]
  }
```

### Architecture

```
apps/api/routers/trends.py          # GET /trends
apps/api/repositories/trends.py     # TrendsRepository — list(season)
apps/api/models/schemas.py          # TrendsResponse, TrendedPlayer (add to existing)
```

### Performance

- Scores are pre-computed (stored in `player_trends`) — no model inference at request time
- Query is a simple SELECT JOIN (players + player_trends)
- No caching needed in v1.0 (scores update once per year)

### Testing

- `tests/routers/test_trends.py` — seed player_trends rows, assert correct response shape and values
- Test null handling: player with no trend score returns nulls, not 500

---

## Milestone 3e — Retraining Workflow

### Goal

Yearly GitHub Actions workflow that re-trains the model at the start of each pre-season (August), ingests the latest full season of data, and updates `player_trends`.

### Workflow

```yaml
# .github/workflows/retrain-trends.yml
name: Retrain Trends Model
on:
  schedule:
    - cron: '0 6 1 8 *'   # August 1, 6am UTC
  workflow_dispatch:        # manual trigger for testing
```

### Steps

1. Run all stat scrapers (NHL.com, MoneyPuck, NST) for completed season
2. Run Hockey Reference historical pull for career SH% update
3. `python -m ml.train --season <completed_season>`
4. `python -m ml.shap_compute --season <next_season>`
5. Upsert `player_trends` rows for upcoming season
6. Slack notification on success/failure

### Testing

- Workflow YAML linting via `actionlint`
- Dry-run test: `workflow_dispatch` with `--dry-run` flag that runs pipeline without writing to DB

---

## Dependencies Between Milestones

```
3a (scrapers + data)
  └─→ 3b (feature engineering requires stat data in DB)
        └─→ 3c (model training requires feature matrix)
              └─→ 3d (inference API requires trained model + player_trends populated)
                    └─→ 3e (retraining workflow wraps 3a → 3c → player_trends upsert)
```

---

## Non-Goals (Deferred to v2.0)

- Layer 2 in-season Z-score engine (TOI, xGF%, Corsi, PP unit changes, shots, line combos)
- Celery nightly re-scoring job
- Combined `pucklogic_trends_score` blending Layer 1 + Layer 2
- Paywall gate on top-10 trending players
- `trending_up_score`, `trending_down_score`, `momentum_score`, `signals_json` columns

---

## Cost Estimate (Zero Users)

| Service | Cost |
|---------|------|
| Railway Hobby (FastAPI backend) | ~$5–10/mo |
| Supabase free tier | $0 |
| Upstash Redis free tier | $0 |
| Vercel Hobby (frontend) | $0 |
| GitHub Actions (cron scrapers) | $0 (public repo) |
| Evolving Hockey data pull | $5 one-time |
| **Total ongoing** | **~$5–10/mo** |

---

## Model Artifact Storage (Decision)

Artifacts are stored in **Supabase Storage** (bucket: `ml-artifacts`, path: `trends/<season>/`). Rationale: Railway dynos are ephemeral; git LFS adds unnecessary repo weight; Supabase Storage is already provisioned and free at this data size (<10MB per model pair).

**Startup loading** (`apps/api/main.py` or a dedicated `ml/loader.py`):
```python
# at FastAPI startup
from ml.loader import load_model_artifacts
model_breakout, model_regression, feature_columns = load_model_artifacts(season=settings.current_season)
```

`load_model_artifacts` downloads from Supabase Storage if `ml/artifacts/` is empty, otherwise loads from disk (cached across requests within a dyno lifetime).

**Failure modes:** Both "artifact missing from storage" and "transient download error" (network failure, credential expiry) are caught in `load_model_artifacts` and raise a `ModelNotAvailableError`. FastAPI startup catches this and sets `model_breakout = model_regression = None`. `GET /trends` checks for None and returns HTTP 503 with `{"detail": "Trends model not available for this season"}` — preventing a crash and giving the frontend a clear signal to hide the Trends panel.

---

## Open Questions

1. **Hockey Reference scraper**: robots.txt allows scraping but requires rate limiting. Confirm scrape cadence (weekly historical pull vs. one-time backfill).
2. **Evolving Hockey $5 pull**: Manual CSV download once per season vs. automated. Start manual for v1.0.
3. **Multi-season historical depth**: How many seasons for training? Recommend 8–10 seasons (2014-15 through 2023-24). Confirm availability for all Tier 1 features back to 2014-15.
