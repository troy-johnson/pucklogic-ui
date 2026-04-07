# PuckLogic Phase 3 — Backend Implementation

## ML Trends Engine (Layer 1) — Pre-Season Breakout/Regression Model

**Timeline:** April – July 2026 (Phase 3)
**Target Release:** v1.0 (September 2026)
**Reference:** `docs/specs/007-feature-engineering-spec.md` · `docs/stats-research.md`

---

## Overview

Phase 3 backend builds the **XGBoost/LightGBM breakout/regression detection model** for pre-season draft guidance. The layer answers: *"Who should I draft?"* by surfacing players trending toward outperformance (breakouts) and underperformance (regression risks) based on 10+ years of NHL historical data and advanced metrics.

**Deliverables:**
1. ✅ Feature engineering pipeline (source data → model inputs)
2. ✅ Model training & hyperparameter optimization
3. ✅ FastAPI inference endpoint (`/api/trends`)
4. ✅ SHAP explainability computation & storage
5. ✅ Yearly retraining pipeline (GitHub Actions cron)
6. ✅ Redis caching for inference results
7. ✅ Test coverage (pytest, mocked data sources)

---

## 1. Data Ingestion & Feature Engineering

### 1.1 Data Sources & Scrapers

All scrapers run on **GitHub Actions cron** (scheduled workflows). Each source has a dedicated script.

| Source | Type | Frequency | Endpoint | Status |
|--------|------|-----------|----------|--------|
| **NHL.com** | Official API | Daily (games, rosters, stats) | `/api/v1/players`, `/api/v1/stats` | ✅ Phase 1 |
| **MoneyPuck** | CSV download | Daily (xG, shots, danger zones) | `moneypuck.com/data.htm` | ✅ Phase 2 |
| **Natural Stat Trick** | HTML scraping | Daily (Corsi, SCF%, on/off splits) | `naturalstattrick.com/playerteams` | ✅ Phase 2 |
| **Hockey Reference** | CSV export + scraping | Weekly (career stats, PDO, age) | `hockey-reference.com/players/` | Phase 3 |
| **DailyFaceoff** | HTML scraping | Weekly (PP unit designation, lines) | `dailyfaceoff.com/nhl/depth-charts` | Phase 3 |
| **Elite Prospects** | HTML scraping / API | Weekly (contract status, ELC flag) | `eliteprospects.com/` | Phase 3 |

**Rate limiting & ethics:** All scrapers must respect `robots.txt`, implement exponential backoff, and include 2–5 second delays between requests.

#### ESPN Category Coverage by Source

The ML model must project all **23 ESPN fantasy scoring categories**. 14 are raw stats stored in `player_stats`; 9 are derived at query time.

| ESPN Category | Raw/Derived | NHL.com API | MoneyPuck | NST | Hockey Ref | Column |
|---------------|-------------|-------------|-----------|-----|------------|--------|
| Goals | Raw | ✅ | ✅ | ✅ | ✅ | `goals` |
| Assists | Raw | ✅ | ✅ | ✅ | ✅ | `assists` |
| Points | **Derived** | — | — | — | — | `= goals + assists` |
| Plus/Minus | Raw | ✅ | — | — | ✅ | `plus_minus` |
| Penalty Minutes | Raw | ✅ | — | — | ✅ | `pim` |
| Power Play Goals | Raw | ✅ | ✅ | ✅ | ✅ | `ppg` |
| Power Play Assists | Raw | ✅ | — | ✅ | ✅ | `ppa` |
| PP Points | **Derived** | — | — | — | — | `= ppg + ppa` |
| Short Handed Goals | Raw | ✅ | — | — | ✅ | `shg` |
| Short Handed Assists | Raw | ✅ | — | — | ✅ | `sha` |
| SH Points | **Derived** | — | — | — | — | `= shg + sha` |
| Game-Winning Goals | Raw | ✅ | — | — | ✅ | `gwg` |
| Faceoffs Won | Raw | ✅ | — | — | ✅ | `fow` |
| Faceoffs Lost | Raw | ✅ | — | — | ✅ | `fol` |
| Shifts | Raw | ✅ | — | — | — | `shifts` |
| Hat Tricks | Raw | ✅ (game log) | — | — | ✅ | `hat_tricks` |
| Shots on Goal | Raw | ✅ | ✅ | ✅ | ✅ | `sog` |
| Hits | Raw | ✅ | — | ✅ | ✅ | `hits` |
| Blocked Shots | Raw | ✅ | — | ✅ | ✅ | `blocked_shots` |
| Defensemen Points | **Derived** | — | — | — | — | `= points WHERE position = 'D'` |
| Special Teams Goals | **Derived** | — | — | — | — | `= ppg + shg` |
| Special Teams Assists | **Derived** | — | — | — | — | `= ppa + sha` |
| Special Teams Points | **Derived** | — | — | — | — | `= stg + sta` |

**NHL.com API is the single source covering all 23 categories.** The existing `NhlComScraper` must be extended to populate full stat lines:
- `/en/skater/summary` — goals, assists, points, +/-, PIM, PPG, PPP, SHG, SHP, GWG, SOG, shifts
- `/en/skater/realtime` — hits, blocked shots
- Game logs (for hat trick counting) — games where a player scored 3+ goals

### 1.2 Feature Computation Pipeline

**Location:** `apps/api/src/services/feature_engineering.py`

**Input:** Raw player stats from all sources (snowflake: one row per player per season).

**Output:** Feature matrix ready for model training.

```python
# Pseudo-code
def compute_features(player_season_df) -> pd.DataFrame:
    """
    Compute Tier 1 & Tier 2 features per feature-engineering-spec.md.
    Input: raw stats from sources.
    Output: feature matrix with all model inputs.
    """

    # RATE STATS (3-year weighted window)
    features["icf_per60"] = compute_icf_per60(player_season_df, window=3)
    features["ixg_per60"] = compute_ixg_per60(player_season_df, window=3)
    features["p1_per60"] = compute_p1_per60(player_season_df, window=3)
    features["scf_per60"] = compute_scf_per60(player_season_df, window=3)

    # POSSESSION & LUCK METRICS
    features["xgf_pct_5v5"] = compute_xgf_pct_5v5(player_season_df)
    features["cf_pct_adj"] = compute_cf_pct_adj(player_season_df)
    features["scf_pct"] = compute_scf_pct(player_season_df)
    features["pdo"] = compute_pdo(player_season_df)

    # SHOOTING PERCENTAGE DELTA (regression signal)
    features["sh_pct_delta"] = compute_sh_pct_delta(player_season_df)
    features["g_minus_ixg"] = compute_g_minus_ixg(player_season_df)  # PRIMARY SIGNAL

    # DEPLOYMENT & CONTEXT
    features["toi_ev_per_game"] = compute_toi_ev_per_game(player_season_df)
    features["toi_pp_per_game"] = compute_toi_pp_per_game(player_season_df)
    features["toi_sh_per_game"] = compute_toi_sh_per_game(player_season_df)
    features["pp_unit"] = extract_pp_unit(player_season_df)  # from DailyFaceoff

    # AGE & POSITION
    features["age"] = extract_age(player_season_df)
    features["position_code"] = extract_position(player_season_df)
    features["nhl_experience"] = compute_nhl_experience(player_season_df)

    # FLAGS
    features["elc_flag"] = extract_elc_status(player_season_df)
    features["post_extension_flag"] = extract_post_extension(player_season_df)

    return features
```

**Minimum thresholds:**
- ES TOI: ≥300 minutes per season (filters noise from depth players)
- Seasons: 10+ years of historical data (2008–2018 training, 2019–2025 validation)

**Data quality checks:**
- NULL handling: impute medians per position group for missing Tier 2+ features
- Outlier detection: flag extreme values (e.g., iCF/60 > 100) for manual review
- Validation: ensure rate stats sum correctly, PDO in reasonable range (0.8–1.2), etc.

### 1.3 Storage

**Location:** `player_stats` table (Supabase PostgreSQL)

Features are materialized and stored per player per season:

```sql
-- Existing columns from Phase 1
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS season SMALLINT;  -- 2008, 2009, ...
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS player_id UUID;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS position_code VARCHAR(2);

-- Tier 1 features (from feature_engineering.py)
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS icf_per60 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS ixg_per60 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS g_minus_ixg FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS xgf_pct_5v5 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS cf_pct_adj FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS scf_per60 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS scf_pct FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS p1_per60 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS toi_ev_per_game FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS toi_pp_per_game FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS toi_sh_per_game FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS pp_unit SMALLINT;           -- 0, 1, or 2
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS pdo FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS sh_pct_delta FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS age SMALLINT;

-- Tier 2 features
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS cf_pct_rel FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS toi_rank_percentile FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS nhl_experience SMALLINT;

-- Context flags
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS elc_flag BOOLEAN;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS post_extension_flag BOOLEAN;

-- ESPN fantasy category columns (14 raw stats — 9 derived at query time)
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS plus_minus INTEGER;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS pim INTEGER;              -- penalty minutes
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS ppg INTEGER;              -- power play goals
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS ppa INTEGER;              -- power play assists
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS shg INTEGER;              -- shorthanded goals
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS sha INTEGER;              -- shorthanded assists
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS gwg INTEGER;              -- game-winning goals
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS fow INTEGER;              -- faceoffs won
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS fol INTEGER;              -- faceoffs lost
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS shifts INTEGER;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS hat_tricks INTEGER;       -- games with 3+ goals (requires game-log query)
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS sog INTEGER;              -- shots on goal
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS hits INTEGER;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS blocked_shots INTEGER;
```

> **Note:** Existing `pp_points` and `sh_points` columns are kept for backward compatibility but are now redundant with `ppg + ppa` and `shg + sha`.

### 1.4 Per-Category Projections Table

**New table: `player_projections`** — separate from `player_trends` (breakout/regression classification).

Stores per-category projected counting stats with model version tracking. This table is the bridge between the ML model outputs and the fantasy scoring engine.

```sql
CREATE TABLE IF NOT EXISTS player_projections (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id       UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  season          TEXT NOT NULL,
  model_version   TEXT NOT NULL,          -- e.g., "2026-09-01"

  -- Raw projected counting stats (14 independent categories)
  proj_goals          NUMERIC(6,1),
  proj_assists        NUMERIC(6,1),
  proj_plus_minus     NUMERIC(6,1),
  proj_pim            NUMERIC(6,1),
  proj_ppg            NUMERIC(6,1),
  proj_ppa            NUMERIC(6,1),
  proj_shg            NUMERIC(6,1),
  proj_sha            NUMERIC(6,1),
  proj_gwg            NUMERIC(6,1),
  proj_fow            NUMERIC(6,1),
  proj_fol            NUMERIC(6,1),
  proj_shifts         NUMERIC(6,1),
  proj_hat_tricks     NUMERIC(6,2),
  proj_sog            NUMERIC(6,1),
  proj_hits           NUMERIC(6,1),
  proj_blocked_shots  NUMERIC(6,1),

  -- Deployment context used for projection
  proj_games          NUMERIC(4,1),     -- projected games played
  proj_toi_ev         NUMERIC(5,1),     -- projected EV TOI total minutes
  proj_toi_pp         NUMERIC(5,1),     -- projected PP TOI total minutes
  proj_toi_sh         NUMERIC(5,1),     -- projected SH TOI total minutes

  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (player_id, season)
);
```

**Derived categories** (computed at API response time, never stored):
- Points = `proj_goals + proj_assists`
- PP Points = `proj_ppg + proj_ppa`
- SH Points = `proj_shg + proj_sha`
- ST Goals = `proj_ppg + proj_shg`
- ST Assists = `proj_ppa + proj_sha`
- ST Points = ST Goals + ST Assists
- Defensemen Points = Points (filtered to `position = 'D'`)

### 1.5 League Scoring Configuration (`user_kits` expansion)

Users must configure their league's scoring settings so projections can be converted to fantasy points.

```sql
ALTER TABLE user_kits ADD COLUMN IF NOT EXISTS league_format TEXT DEFAULT 'points'
  CHECK (league_format IN ('points', 'roto', 'head_to_head'));

ALTER TABLE user_kits ADD COLUMN IF NOT EXISTS scoring_settings JSONB DEFAULT '{}';
```

**`scoring_settings` JSON structure:**

```json
{
  "categories": {
    "goals": 6.0,
    "assists": 4.0,
    "points": 0,
    "plus_minus": 2.0,
    "pim": 0.5,
    "ppg": 2.0,
    "ppa": 1.0,
    "pp_points": 0,
    "shg": 4.0,
    "sha": 2.0,
    "sh_points": 0,
    "gwg": 2.0,
    "fow": 0.25,
    "fol": -0.25,
    "shifts": 0,
    "hat_tricks": 5.0,
    "sog": 0.9,
    "hits": 1.0,
    "blocked_shots": 1.0,
    "defensemen_points": 0,
    "st_goals": 0,
    "st_assists": 0,
    "st_points": 0
  },
  "preset": "espn_default"
}
```

**Built-in presets** (server-side constants in `apps/api/src/services/scoring_presets.py`):

| Preset | Platform | Description |
|--------|----------|-------------|
| `espn_default` | ESPN | Standard ESPN points league values |
| `yahoo_default` | Yahoo | Yahoo's default scoring |
| `fantrax_default` | Fantrax | Fantrax default scoring |
| `espn_roto` | ESPN | All 23 categories active, no point values (Z-score mode) |
| `custom` | Any | User-defined values |

---

## 2. Model Training Pipeline

### 2.1 Training Data & Label Construction

**Location:** `apps/api/src/ml/training.py`

**Label definition:**
- **"Breakout"**: player scores ≥20% more fantasy points than trailing 2-season average
- **"Regression"**: player scores ≥20% fewer fantasy points than trailing 2-season average
- **"Neutral"**: all others

```python
def construct_labels(player_stats_df) -> pd.DataFrame:
    """
    Compute fantasy point baseline and classify breakout/regression.
    """
    player_stats_df = player_stats_df.sort_values(["player_id", "season"])

    # Compute trailing 2-season average fantasy points (position-weighted)
    player_stats_df["trailing_2yr_pts"] = player_stats_df.groupby("player_id")["fantasy_pts"].transform(
        lambda x: x.rolling(window=2, min_periods=1).mean().shift(1)
    )

    # Compute deltas
    player_stats_df["pct_change"] = (
        (player_stats_df["fantasy_pts"] - player_stats_df["trailing_2yr_pts"]) /
        player_stats_df["trailing_2yr_pts"]
    )

    # Classify
    def classify_label(row):
        if pd.isna(row["trailing_2yr_pts"]):
            return "neutral"  # Insufficient history (rookie)
        pct = row["pct_change"]
        if pct >= 0.20:
            return "breakout"
        elif pct <= -0.20:
            return "regression"
        else:
            return "neutral"

    player_stats_df["label"] = player_stats_df.apply(classify_label, axis=1)
    return player_stats_df
```

**Train/validate split:**
- **Training:** seasons 2008–2022 (~15 years)
- **Validation:** seasons 2023–2025 (~3 years)
- **Test:** hold out 2024–25 season for final eval

**Class balance:** Likely skewed toward "neutral" — use `class_weight="balanced"` in XGBoost.

### 2.2 Model Selection & Training

**Algorithm:** XGBoost or LightGBM (gradient boosted trees)
- **Why?** Fast, no GPU required, excellent for tabular data, SHAP explainability built-in
- **Hyperparameters:** See `apps/api/src/ml/hyperparams.py`

```python
# Location: apps/api/src/ml/training.py

def train_breakout_model(features_df, labels_series) -> xgb.XGBClassifier:
    """
    Train XGBoost classifier for breakout/regression detection.
    """
    X = features_df[TIER1_FEATURES + TIER2_FEATURES]  # defined in config
    y = labels_series

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        class_weight="balanced",
        objective="multi:softmax",
        num_class=3,  # breakout, neutral, regression
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        early_stopping_rounds=50,
        verbose=10,
    )

    # Validate
    y_pred = model.predict(X_val)
    print(f"Validation accuracy: {accuracy_score(y_val, y_pred):.3f}")
    print(f"Precision (breakout): {precision_score(y_val, y_pred, labels=['breakout'], zero_division=0):.3f}")
    print(f"Recall (regression): {recall_score(y_val, y_pred, labels=['regression'], zero_division=0):.3f}")

    return model
```

**Output:** Serialized model saved to `apps/api/src/ml/models/breakout_model.joblib`

### 2.3 Feature Importance & SHAP Explainability

**Location:** `apps/api/src/ml/explainability.py`

```python
def compute_shap_values(model, X_val) -> Dict[str, Any]:
    """
    Compute SHAP values for each prediction.

    Returns:
      {
        "model_feature_importance": {...},      # XGBoost built-in
        "shap_base_value": <float>,             # model's average prediction
        "shap_values_per_player": {
          player_id: {
            "top_3_contributors": [
              {"feature": "g_minus_ixg", "shap_value": 0.45},
              {"feature": "pp_unit", "shap_value": 0.32},
              {"feature": "age", "shap_value": -0.12},
            ]
          }
        }
      }
    """
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_val)  # shape: (n_samples, n_features)

    feature_importance = dict(zip(X_val.columns, model.feature_importances_))

    shap_per_player = {}
    for idx, player_id in enumerate(X_val.index):  # assume index is player_id
        player_shap = shap_values[idx]
        top_3_indices = np.argsort(np.abs(player_shap))[-3:][::-1]

        shap_per_player[player_id] = {
            "top_3_contributors": [
                {
                    "feature": X_val.columns[i],
                    "shap_value": float(player_shap[i]),
                }
                for i in top_3_indices
            ]
        }

    return {
        "model_feature_importance": feature_importance,
        "shap_base_value": float(explainer.expected_value),
        "shap_values_per_player": shap_per_player,
    }
```

**Storage:** Computed at training time, cached in Supabase `player_trends.shap_top3` (JSONB).

### 2.4 Per-Category Projection Models (Multi-Output Regression)

In addition to the breakout/regression classifier (Section 2.2), Phase 3 includes **3 multi-output regression models** that predict individual stat categories for all 850+ eligible players.

**Why 3 models instead of 14 or 1?**
- **Not 14 independent models:** Cross-category correlations are real (more goals → more GWG). Multi-output captures these.
- **Not 1 giant model:** Peripheral stats (hits, blocks) have fundamentally different feature importance from scoring stats. Lumping them degrades both.
- **3 groups** is the sweet spot — categories with shared feature drivers are grouped together.

| Model | Targets | Feature Focus | Rationale |
|-------|---------|---------------|-----------|
| **Scoring** | G, A, PPG, PPA, SHG, SHA, GWG, SOG | Shot generation, xG, PP deployment, aging | Correlated offensive stats; shared feature drivers |
| **Peripheral** | Hits, BLK, PIM, Shifts | Team system, physicality, position, role | Identity/deployment stats; low correlation with scoring |
| **Volume** | FOW, FOL, Hat Tricks, +/- | FO skill (centers only), goal distribution, team quality | Distinct stat types; FOW/FOL center-specific |

**Implementation:**

```python
# apps/api/src/ml/projection_models.py

from sklearn.multioutput import MultiOutputRegressor
import xgboost as xgb

SCORING_TARGETS = ["goals", "assists", "ppg", "ppa", "shg", "sha", "gwg", "sog"]
PERIPHERAL_TARGETS = ["hits", "blocked_shots", "pim", "shifts"]
VOLUME_TARGETS = ["fow", "fol", "hat_tricks", "plus_minus"]

def train_scoring_model(features_df, targets_df):
    """Multi-output regression for correlated offensive stats."""
    model = MultiOutputRegressor(
        xgb.XGBRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
        )
    )
    model.fit(features_df, targets_df[SCORING_TARGETS])
    return model

def train_peripheral_model(features_df, targets_df):
    """Multi-output regression for role/physicality stats."""
    model = MultiOutputRegressor(
        xgb.XGBRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
        )
    )
    model.fit(features_df, targets_df[PERIPHERAL_TARGETS])
    return model

def train_volume_model(features_df, targets_df):
    """Multi-output regression for faceoffs, hat tricks, +/-."""
    # Filter to centers only for FOW/FOL features
    model = MultiOutputRegressor(
        xgb.XGBRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
        )
    )
    model.fit(features_df, targets_df[VOLUME_TARGETS])
    return model

def project_all_categories(player_features, models) -> dict:
    """
    Run all 3 models and assemble per-category projections.
    Derived categories (Points, PPP, SHP, STP, Defensemen Points)
    are computed from raw outputs — never predicted directly.
    """
    scoring_preds = models["scoring"].predict(player_features)
    peripheral_preds = models["peripheral"].predict(player_features)
    volume_preds = models["volume"].predict(player_features)

    raw = {
        **dict(zip(SCORING_TARGETS, scoring_preds[0])),
        **dict(zip(PERIPHERAL_TARGETS, peripheral_preds[0])),
        **dict(zip(VOLUME_TARGETS, volume_preds[0])),
    }

    # Clamp to reasonable ranges (no negative goals, etc.)
    for key in raw:
        raw[key] = max(0, round(raw[key], 1))

    return raw
```

**Projection pipeline (extends feature-engineering-spec.md Step 5):**

1. Compute per-category **rate stats** (goals/60, assists/60, hits/60, etc.) using 3-year weighted window
2. Regress shooting percentage toward career mean (for goals specifically)
3. Project **TOI by situation** (EV, PP, SH) using aging curves + context flags
4. Run each model group → per-category projected counting stats
5. Clamp projections to reasonable ranges
6. Store in `player_projections` table

### 2.5 Fantasy Scoring Service

**Location:** `apps/api/src/services/fantasy_scoring.py`

Converts per-category projections into fantasy points using the user's league scoring settings.

```python
# apps/api/src/services/fantasy_scoring.py

DERIVED_CATEGORIES = {
    "points": lambda p: p["goals"] + p["assists"],
    "pp_points": lambda p: p["ppg"] + p["ppa"],
    "sh_points": lambda p: p["shg"] + p["sha"],
    "st_goals": lambda p: p["ppg"] + p["shg"],
    "st_assists": lambda p: p["ppa"] + p["sha"],
    "st_points": lambda p: p["ppg"] + p["shg"] + p["ppa"] + p["sha"],
    # defensemen_points handled via position filter
}

def compute_fantasy_points(
    projections: dict[str, float],
    scoring_settings: dict[str, float],
    position: str,
) -> float:
    """
    fantasy_pts = SUM(projected_stat × league_weight) for each active category.
    """
    # Expand raw projections with derived categories
    full_projections = {**projections}
    for cat, fn in DERIVED_CATEGORIES.items():
        full_projections[cat] = fn(projections)

    # Defensemen Points: only count if player is a D
    if position != "D":
        full_projections["defensemen_points"] = 0
    else:
        full_projections["defensemen_points"] = full_projections["points"]

    total = 0.0
    for category, weight in scoring_settings.items():
        if weight != 0 and category in full_projections:
            total += full_projections[category] * weight

    return round(total, 1)


def compute_roto_zscores(
    all_projections: list[dict],
    active_categories: list[str],
) -> list[dict]:
    """
    For roto leagues: compute Z-score per category across the player pool.
    Returns total Z-score per player.
    """
    import numpy as np

    # Compute mean and stddev per category
    for cat in active_categories:
        values = [p["projections"][cat] for p in all_projections]
        mean = np.mean(values)
        std = np.std(values) or 1.0  # avoid division by zero

        for player in all_projections:
            player["z_scores"][cat] = (player["projections"][cat] - mean) / std

    # Sum Z-scores
    for player in all_projections:
        player["total_z"] = sum(player["z_scores"].values())

    return sorted(all_projections, key=lambda p: p["total_z"], reverse=True)


def compute_vorp(
    scored_players: list[dict],
    league_format: str,
) -> list[dict]:
    """
    VORP = player_value - replacement_level_value.
    Replacement level defaults (12-team league):
      - Forwards: rank 150
      - Defensemen: rank 60
    """
    forwards = [p for p in scored_players if p["position"] in ("C", "LW", "RW")]
    defensemen = [p for p in scored_players if p["position"] == "D"]

    value_key = "fantasy_pts" if league_format == "points" else "total_z"

    forwards.sort(key=lambda p: p[value_key], reverse=True)
    defensemen.sort(key=lambda p: p[value_key], reverse=True)

    f_replacement = forwards[149][value_key] if len(forwards) > 149 else 0
    d_replacement = defensemen[59][value_key] if len(defensemen) > 59 else 0

    for p in forwards:
        p["vorp"] = round(p[value_key] - f_replacement, 1)
    for p in defensemen:
        p["vorp"] = round(p[value_key] - d_replacement, 1)

    all_players = forwards + defensemen
    all_players.sort(key=lambda p: p["vorp"], reverse=True)
    return all_players
```

**Updated rankings pipeline (end-to-end):**

```
1. Source weighting (existing Phase 2) → composite_rank per player
2. Fetch player_projections for the season
3. For each player:
   a. Compute derived categories from raw projections
   b. If league_format == "points":
      fantasy_pts = SUM(proj_category × scoring_weight)
   c. If league_format == "roto":
      z_score_per_cat = (player_proj - pool_mean) / pool_stddev
      total_z = SUM(z_scores)
4. Compute VORP = player_value - replacement_level (by position)
5. Final ranking = sort by VORP descending
```

---

## 3. FastAPI Inference Endpoint

### 3.1 Route: `GET /api/trends`

**Location:** `apps/api/src/routers/trends.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient
import joblib
import json

router = APIRouter(prefix="/api/trends", tags=["Trends"])

# Load model at startup
MODEL = None

async def load_model():
    global MODEL
    if MODEL is None:
        MODEL = joblib.load("src/ml/models/breakout_model.joblib")

@router.get("/")
async def get_trends(
    season: int = 2026,
    position: Optional[str] = None,  # "F", "D", or None for all
    skip: int = 0,
    limit: int = 100,
    db: AsyncClient = Depends(get_db),
) -> Dict[str, Any]:
    """
    Fetch pre-season breakout/regression trends for the given season.

    Returns top candidates sorted by |breakout_score - regression_risk|.

    Query parameters:
      - season: NHL season (default: 2026)
      - position: "F" or "D" (optional filter)
      - skip / limit: pagination

    Response:
      {
        "season": 2026,
        "total_count": 850,
        "players": [
          {
            "player_id": "...",
            "name": "Connor McDavid",
            "position": "C",
            "age": 25,
            "team": "EDM",
            "breakout_score": 0.87,
            "regression_risk": 0.12,
            "confidence": "HIGH",
            "projections": {
              "goals": 52.3, "assists": 81.2, "points": 133.5,
              "plus_minus": 28.4, "pim": 18.0,
              "ppg": 14.1, "ppa": 28.7, "pp_points": 42.8,
              "shg": 1.2, "sha": 0.8, "sh_points": 2.0,
              "gwg": 8.1, "fow": 812.0, "fol": 704.0,
              "shifts": 1648.0, "hat_tricks": 2.1,
              "sog": 312.4, "hits": 42.0, "blocked_shots": 18.0,
              "st_goals": 15.3, "st_assists": 29.5, "st_points": 44.8,
              "defensemen_points": 0
            },
            "fantasy_pts": 287.5,
            "vorp": 142.3,
            "shap_top3": [
              {"feature": "g_minus_ixg", "contribution": 0.45},
              {"feature": "pp_unit", "contribution": 0.32},
              {"feature": "age", "contribution": -0.12}
            ]
          },
          ...
        ]
      }
    """
    await load_model()

    # Fetch player trends + projections from DB
    query = db.table("player_trends").select(
        "player_id, players(name, position, age, team), "
        "breakout_score, regression_risk, confidence, shap_top3, "
        "player_projections(proj_goals, proj_assists, proj_plus_minus, "
        "proj_pim, proj_ppg, proj_ppa, proj_shg, proj_sha, proj_gwg, "
        "proj_fow, proj_fol, proj_shifts, proj_hat_tricks, proj_sog, "
        "proj_hits, proj_blocked_shots, proj_games)"
    ).eq("season", season)

    if position:
        query = query.eq("players.position", position)

    result = await query.order_by("breakout_score", desc=True).range(skip, skip + limit)

    return {
        "season": season,
        "total_count": len(result.data),  # ideally: use COUNT query
        "players": result.data,
    }
```

**Authentication:** Protected by JWT guard (see CLAUDE.md). Free tier receives full access v1.0 (paywalled in Layer 2 v2.0).

### 3.2 Pre-computation vs. On-Demand Inference

**Approach (recommended):** **Pre-compute at training time**, cache in DB.

- Training job runs annually (pre-season cron)
- Computes scores for all 850+ eligible players in ~5 seconds (joblib + vectorized SHAP)
- Stores results in `player_trends` table with `updated_at` timestamp
- API reads cached results → zero latency

**Alternative (if needed):** On-demand inference (slower, but allows runtime feature updates).

---

## 4. Celery Job: Annual Retraining Pipeline

### 4.1 Trigger: GitHub Actions Workflow

**Location:** `.github/workflows/ml-train-annual.yml`

```yaml
name: Annual ML Model Retraining

on:
  schedule:
    - cron: "0 2 1 Sep *"  # September 1, 2:00 AM UTC (pre-season, post-trades)
  workflow_dispatch:        # Manual trigger

jobs:
  train:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd apps/api
          pip install -e ".[ml]"

      - name: Fetch training data
        run: |
          python -m src.ml.scripts.fetch_training_data \
            --start_season 2008 \
            --end_season 2025

      - name: Train model
        run: |
          python -m src.ml.scripts.train_model \
            --output_path src/ml/models/breakout_model.joblib

      - name: Compute SHAP values & populate DB
        run: |
          python -m src.ml.scripts.compute_shap_and_populate_db \
            --season 2026 \
            --db_url ${{ secrets.SUPABASE_DATABASE_URL }}

      - name: Run validation tests
        run: pytest tests/ml/ -v

      - name: Upload model artifact
        uses: actions/upload-artifact@v3
        with:
          name: breakout-model-${{ github.run_id }}
          path: apps/api/src/ml/models/breakout_model.joblib
```

### 4.2 Celery Tasks (Optional: Layer 2 In-Season Updates)

**Location:** `apps/api/src/celery_tasks/ml_jobs.py`

```python
from celery import shared_task
from apps.api.src.ml import training, explainability
from supabase import AsyncClient

@shared_task(bind=True)
def retrain_model_task(self):
    """
    Async task to retrain model (triggered by webhook or cron).
    """
    try:
        # Fetch training data
        features_df, labels_df = training.fetch_and_prepare_data(
            start_season=2008,
            end_season=2025,
        )

        # Train
        model = training.train_breakout_model(features_df, labels_df)
        model.save("src/ml/models/breakout_model.joblib")

        # SHAP
        shap_output = explainability.compute_shap_values(model, features_df)

        # Populate DB
        db = AsyncClient(supabase_url=..., supabase_key=...)
        for player_id, shap_data in shap_output["shap_values_per_player"].items():
            db.table("player_trends").update({
                "shap_top3": shap_data["top_3_contributors"],
                "updated_at": "now()",
            }).eq("player_id", player_id).execute()

        return {"status": "success", "model_path": "src/ml/models/breakout_model.joblib"}

    except Exception as e:
        self.retry(exc=e, countdown=300)  # retry in 5 min
```

---

## 5. Testing

### 5.1 Unit Tests

**Location:** `apps/api/tests/ml/`

```
tests/ml/
├── test_feature_engineering.py      # Feature computation correctness
├── test_model_training.py           # Training pipeline, label construction
├── test_shap_explainability.py      # SHAP value computation
├── test_projection_models.py        # Per-category multi-output regression models
├── test_fantasy_scoring.py          # Fantasy point computation, roto Z-scores, VORP
├── test_inference.py                # FastAPI /trends endpoint
└── conftest.py                      # Fixtures (mock player data)
```

**Minimum coverage:**
- Feature computation: test each tier 1 feature against manual calculation
- Label construction: verify ≥20% threshold correctly classifies breakout/regression
- Model inference: ensure predictions in [0, 1] range, probabilities sum to 1
- SHAP: top-3 contributors match model's feature importance, no NaNs
- Per-category projections: all 14 raw output categories are non-negative; derived categories match formulas
- Fantasy scoring: point-league totals match manual calculations; roto Z-scores sum correctly; VORP ranks sensibly
- API: test pagination, position filtering, per-category projections in response, auth guards

```python
# test_feature_engineering.py
def test_icf_per60_computation():
    """Verify iCF/60 = (3yr_weighted_icf) / (3yr_weighted_toi) * 60"""
    mock_player = {
        "season_2025": {"icf": 1200, "toi_es": 1440},  # 50 min ES
        "season_2024": {"icf": 1150, "toi_es": 1380},
        "season_2023": {"icf": 1100, "toi_es": 1320},
    }

    result = feature_engineering.compute_icf_per60(mock_player)
    expected = (1200 * 0.5 + 1150 * 0.3 + 1100 * 0.2) / (1440 * 0.5 + 1380 * 0.3 + 1320 * 0.2) * 60
    assert abs(result - expected) < 0.01


# test_projection_models.py
def test_project_all_categories_non_negative():
    """All raw projected stats must be >= 0 after clamping."""
    mock_features = pd.DataFrame([MOCK_PLAYER_FEATURES])
    result = project_all_categories(mock_features, MOCK_MODELS)
    for cat, val in result.items():
        assert val >= 0, f"{cat} projected negative: {val}"


def test_scoring_model_targets():
    """Scoring model outputs exactly the 8 SCORING_TARGETS categories."""
    mock_features = pd.DataFrame([MOCK_PLAYER_FEATURES])
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([[30, 50, 10, 18, 1, 1, 5, 220]])
    result = dict(zip(SCORING_TARGETS, mock_model.predict(mock_features)[0]))
    assert set(result.keys()) == set(SCORING_TARGETS)


def test_peripheral_model_targets():
    """Peripheral model outputs exactly the 4 PERIPHERAL_TARGETS categories."""
    mock_features = pd.DataFrame([MOCK_PLAYER_FEATURES])
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([[80, 120, 55, 1400]])
    result = dict(zip(PERIPHERAL_TARGETS, mock_model.predict(mock_features)[0]))
    assert set(result.keys()) == set(PERIPHERAL_TARGETS)


# test_fantasy_scoring.py
def test_compute_fantasy_points_points_league():
    """Verify fantasy_pts = SUM(projected_stat × weight) for all active categories."""
    projections = {
        "goals": 30, "assists": 50, "plus_minus": 15, "pim": 20,
        "ppg": 10, "ppa": 18, "shg": 1, "sha": 1, "gwg": 5,
        "fow": 600, "fol": 500, "shifts": 1200, "hat_tricks": 1,
        "sog": 220, "hits": 80, "blocked_shots": 100,
    }
    scoring = {
        "goals": 6.0, "assists": 4.0, "plus_minus": 2.0, "pim": 0.5,
        "ppg": 2.0, "ppa": 1.0, "shg": 4.0, "sha": 2.0, "gwg": 2.0,
        "fow": 0.25, "fol": -0.25, "hat_tricks": 5.0, "sog": 0.9,
        "hits": 1.0, "blocked_shots": 1.0,
    }
    result = compute_fantasy_points(projections, scoring, position="C")
    expected = (30*6 + 50*4 + 15*2 + 20*0.5 + 10*2 + 18*1 + 1*4 + 1*2 + 5*2
                + 600*0.25 + 500*(-0.25) + 1*5 + 220*0.9 + 80*1 + 100*1)
    assert abs(result - expected) < 0.1


def test_defensemen_points_only_for_defense():
    """defensemen_points must be 0 for forwards, equal to points for defenders."""
    projections = {"goals": 10, "assists": 20, **{k: 0 for k in ["plus_minus", "pim", "ppg",
                   "ppa", "shg", "sha", "gwg", "fow", "fol", "shifts", "hat_tricks",
                   "sog", "hits", "blocked_shots"]}}
    scoring = {"defensemen_points": 1.0}

    fwd_pts = compute_fantasy_points(projections, scoring, position="C")
    def_pts = compute_fantasy_points(projections, scoring, position="D")

    assert fwd_pts == 0.0
    assert def_pts == 30.0  # 10 goals + 20 assists


def test_roto_zscores_centered_at_zero():
    """Z-scores across the player pool must have mean ≈ 0 per category."""
    import numpy as np
    players = [
        {"projections": {"goals": g}, "z_scores": {}}
        for g in [20, 30, 40, 50, 60]
    ]
    result = compute_roto_zscores(players, active_categories=["goals"])
    z_values = [p["z_scores"]["goals"] for p in result]
    assert abs(np.mean(z_values)) < 1e-9


def test_vorp_replacement_level_forward():
    """Rank-150 forward defines replacement level; player above scores positive VORP."""
    scored_players = [
        {"position": "C", "fantasy_pts": float(100 - i), "vorp": 0.0}
        for i in range(300)
    ]
    result = compute_vorp(scored_players, league_format="points")
    replacement_val = result[149]["fantasy_pts"]
    assert result[0]["vorp"] > 0
    assert abs(result[149]["vorp"]) < 0.01  # replacement player itself → VORP ≈ 0
```

### 5.2 Integration Tests

**Location:** `apps/api/tests/ml/test_integration.py`

- End-to-end: raw stats → features → projection models → fantasy scoring → DB storage
- Mock all external sources (MoneyPuck CSV, NST scrape, etc.)
- Validate projection outputs make sense (e.g., top-line center projects more goals than 4th-line grinder)
- Validate model outputs make sense (e.g., young high-TOI forwards have higher breakout scores)
- Full `/api/trends` response shape matches schema — all 23 ESPN categories present, derived categories computed correctly

---

## 6. Deployment & Monitoring

### 6.1 Model Versioning

Store trained models in Supabase Storage (or S3):

```python
# apps/api/src/ml/storage.py
def upload_model_to_storage(model_path: str, version: str):
    """Upload joblib model to Supabase Storage."""
    storage_path = f"ml-models/breakout_model_{version}.joblib"
    with open(model_path, "rb") as f:
        supabase.storage.from_("ml-models").upload(storage_path, f)
    return storage_path
```

Version naming: `breakout_model_2026-07-31.joblib` (date of retraining).

### 6.2 Logging & Monitoring

**Log training metrics to Supabase `ml_training_logs` table:**

```python
def log_training_metrics(metrics: Dict[str, float]):
    """Record accuracy, precision, recall, F1 per class."""
    db.table("ml_training_logs").insert({
        "model_name": "breakout_regression_xgboost",
        "trained_at": "now()",
        "metrics": metrics,  # JSON
        "model_version": "2026-07-31",
    }).execute()
```

**Alert on retraining failures:** GitHub Actions workflow can send Slack notifications on failure.

---

## 7. Rollout Plan

### Phase 3a (May 2026): Development
- ✅ Implement feature engineering pipeline
- ✅ Train breakout/regression classifier on historical data (2008–2025)
- ✅ Train per-category projection models (scoring / peripheral / volume)
- ✅ Implement fantasy scoring service (`compute_fantasy_points`, roto Z-scores, VORP)
- ✅ Expand `player_stats` with full 14-column ESPN category coverage
- ✅ Create `player_projections` table
- ✅ Expand `user_kits` with `scoring_settings` JSONB and `league_format`
- ✅ Compute SHAP values
- ✅ Implement FastAPI `/trends` endpoint (with per-category projections in response)
- ✅ Write unit & integration tests

### Phase 3b (June 2026): QA & Optimization
- ✅ Hyperparameter tuning via cross-validation
- ✅ Validate model outputs against domain knowledge
- ✅ Set up annual retraining GitHub Actions workflow
- ✅ Integration test with frontend (Phase 3 frontend team)

### Phase 3c (July 2026): Pre-Season Launch
- ✅ Run final training on 2008–2025 data
- ✅ Deploy to production (`/api/trends`)
- ✅ Monitor inference latency & cache hit rates
- ✅ Frontend surfaces SHAP explainability on rankings dashboard

---

## Critical Success Metrics

| Metric | Target | Owner |
|--------|--------|-------|
| Model accuracy (validation 2023–25) | ≥75% (neutral 60%, breakout/regression 45%+) | ML |
| Inference latency | <50ms per player (cached) | Backend |
| SHAP computation time | <5 sec for 850 players | ML |
| Precision (breakout candidates) | ≥60% | Validation |
| Test coverage | ≥85% (ML module) | Backend |

---

## Appendix: Key Files

| File | Purpose |
|------|---------|
| `apps/api/src/services/feature_engineering.py` | Feature computation pipeline |
| `apps/api/src/ml/training.py` | Model training & label construction |
| `apps/api/src/ml/explainability.py` | SHAP value computation |
| `apps/api/src/ml/projection_models.py` | Per-category multi-output regression models (scoring / peripheral / volume) |
| `apps/api/src/services/fantasy_scoring.py` | Fantasy point computation, roto Z-scores, VORP |
| `apps/api/src/services/scoring_presets.py` | Built-in league scoring presets (ESPN, Yahoo, Fantrax, roto) |
| `apps/api/src/ml/models/breakout_model.joblib` | Serialized trained classifier |
| `apps/api/src/ml/models/scoring_model.joblib` | Serialized scoring projection model |
| `apps/api/src/ml/models/peripheral_model.joblib` | Serialized peripheral projection model |
| `apps/api/src/ml/models/volume_model.joblib` | Serialized volume projection model |
| `apps/api/src/routers/trends.py` | FastAPI `/api/trends` endpoint |
| `.github/workflows/ml-train-annual.yml` | Annual retraining trigger |
| `apps/api/tests/ml/` | All ML unit & integration tests |
| `docs/specs/007-feature-engineering-spec.md` | Feature reference (this document builds on it) |
| `docs/stats-research.md` | Methodology & source citations |

---

## Layer 2b — In-Season Projection Recalibration (v2.0)

> **Scope:** v2.0 post-launch feature. Document here to preserve design intent.

### Problem Statement

Layer 1 produces a pre-season projection (e.g., "41 projected fantasy points"). Once the season starts, that number becomes stale. A player unexpectedly producing at a 70-point pace through 25 games needs a different question answered: *"Is this real, or is he running hot?"*

Layer 2 (leading indicators) captures *process signals* — TOI, xGF%, PP unit moves — that precede production. Layer 2b captures something different: **Bayesian updating of the counting-stat projection itself** based on actual games played.

This drives mid-season waiver wire and trade guidance — the in-season analogs to draft guidance.

---

### How It Works

**Core idea:** Treat the Layer 1 pre-season projection as a **Bayesian prior**. As games are played, update that prior with actual YTD production, weighted by sample size. Small sample = trust the prior heavily. Large sample = let actual pace dominate.

```python
def recalibrate_projection(
    prior_pts: float,       # Layer 1 pre-season projection (e.g., 41)
    ytd_pace: float,        # Current season pace extrapolated to 82 games
    games_played: int,      # Sample size
    total_games: int = 82,
) -> dict:
    """
    Bayesian blend of pre-season prior and in-season pace.

    Weight scheme:
      - 0–10 games: 85% prior / 15% pace  (tiny sample)
      - 11–25 games: 60% prior / 40% pace
      - 26–50 games: 35% prior / 65% pace
      - 51+ games:   15% prior / 85% pace  (large sample, pace dominates)
    """
    prior_weight = max(0.15, 0.85 - (games_played / total_games) * 0.70)
    pace_weight = 1.0 - prior_weight

    recalibrated_pts = (prior_pts * prior_weight) + (ytd_pace * pace_weight)

    # Sustainability signal: how far above/below xG is the actual pace?
    sustainability_flag = assess_sustainability(ytd_pace, prior_pts, games_played)

    return {
        "recalibrated_projection": round(recalibrated_pts, 1),
        "prior_projection": prior_pts,
        "ytd_pace": ytd_pace,
        "games_played": games_played,
        "prior_weight": round(prior_weight, 2),
        "sustainability_flag": sustainability_flag,  # "LIKELY_REAL" | "RUNNING_HOT" | "BELOW_EXPECTATIONS"
    }
```

**Sustainability signal** uses Layer 2 process signals to classify the pace:
- `LIKELY_REAL` — Layer 2 signals (TOI, PP unit, xGF%) support the pace
- `RUNNING_HOT` — pace above xG, PDO elevated, no process change; expect regression
- `BELOW_EXPECTATIONS` — pace below projection but Layer 2 signals are neutral/positive; hold

---

### New Columns: `player_trends`

```sql
-- In-season projection recalibration outputs
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS recalibrated_projection FLOAT;  -- Bayesian blended pts
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS ytd_pace FLOAT;                  -- current season pace (82-game)
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS games_played SMALLINT;
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS prior_weight FLOAT;              -- how much prior dominates
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS sustainability_flag VARCHAR(20); -- LIKELY_REAL / RUNNING_HOT / BELOW_EXPECTATIONS
```

---

### Celery Job: Nightly Recalibration

Runs nightly after games complete (same cadence as Layer 2 job):

```python
@shared_task
def recalibrate_projections_task():
    """
    Nightly: fetch YTD stats, recompute Bayesian blend, update player_trends.
    """
    players = db.table("player_trends").select(
        "player_id, projection_pts, games_played"
    ).execute()

    for player in players.data:
        ytd_stats = fetch_ytd_stats(player["player_id"])  # from NHL.com API
        ytd_pace = (ytd_stats["fantasy_pts"] / ytd_stats["games_played"]) * 82

        result = recalibrate_projection(
            prior_pts=player["projection_pts"],
            ytd_pace=ytd_pace,
            games_played=ytd_stats["games_played"],
        )

        db.table("player_trends").update({
            "recalibrated_projection": result["recalibrated_projection"],
            "ytd_pace": result["ytd_pace"],
            "games_played": result["games_played"],
            "prior_weight": result["prior_weight"],
            "sustainability_flag": result["sustainability_flag"],
            "updated_at": "now()",
        }).eq("player_id", player["player_id"]).execute()
```

---

### API Extension: `GET /api/trends` (in-season mode)

When `games_played > 0`, the response adds recalibration fields:

```json
{
  "player_id": "...",
  "name": "Brayden Point",
  "breakout_score": 0.72,
  "projection_pts": 68.0,
  "recalibrated_projection": 81.5,
  "ytd_pace": 87.2,
  "games_played": 31,
  "prior_weight": 0.35,
  "sustainability_flag": "LIKELY_REAL"
}
```

---

### Use Cases This Enables

| Scenario | Signal | Guidance |
|----------|--------|----------|
| Player on 70pt pace, projected 41 | `LIKELY_REAL`, Layer 2 signals positive | **Trade target / hold** |
| Player on 70pt pace, projected 41 | `RUNNING_HOT`, elevated PDO, no PP move | **Sell high / regression incoming** |
| Player on 20pt pace, projected 50 | Layer 2 neutral, aging D | **Drop / sell** |
| Player on 25pt pace, projected 50 | `BELOW_EXPECTATIONS`, PP demotion | **Buy low if PP role returns** |

---

### Monetization Gate (v2.0)

Same gate as Layer 2 leading indicators:
- **Free tier:** recalibrated projections visible but top-10 `sustainability_flag = LIKELY_REAL` are paywalled
- **Paid tier:** full access including sustainability breakdowns

---

### Key Files (v2.0)

| File | Purpose |
|------|---------|
| `apps/api/src/ml/recalibration.py` | Bayesian blending logic |
| `apps/api/src/celery_tasks/recalibration_jobs.py` | Nightly recalibration task |
| `apps/api/tests/ml/test_recalibration.py` | Unit tests |

---

*See also: `docs/phase-3-frontend.md` (SHAP UI integration)*
