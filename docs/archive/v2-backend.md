# PuckLogic v2.0 — Backend Implementation

## In-Season Leading Indicator Engine (Layer 2)

**Timeline:** Post-launch (after v1.0 September 2026 release)
**Target Release:** v2.0 (TBD — in-season 2026–27)
**Reference:** `docs/phase-3-backend.md` · `docs/specs/007-feature-engineering-spec.md` · `docs/stats-research.md`

---

## Overview

v2.0 backend builds the **Layer 2 in-season leading indicator engine** — the primary differentiator vs. ESPN/Yahoo last-7-days stats. It answers: *"Who should I pick up before anyone else notices?"* by surfacing process improvements that precede realized production, so users act before the waiver wire runs on a player.

Layer 2 runs as a **nightly Celery job** that computes 14-day rolling Z-scores for 8 leading indicator signals, stores per-signal explainability data in `signals_json`, and blends the result with the Layer 1 breakout score into a unified `pucklogic_trends_score`. The `/api/trends` endpoint is updated to serve Layer 2 data with a subscription gate: top-10 players by `pucklogic_trends_score` are paywalled for free-tier users.

**Deliverables (all planned — v2.0 is post-launch):**
1. ☐ 14-day rolling Z-score computation for all 8 leading indicator signals
2. ☐ Nightly Celery job to refresh rolling stats and re-score all active players
3. ☐ `player_trends` table updates: `trending_up_score`, `trending_down_score`, `momentum_score`, `signals_json`, `window_days`
4. ☐ Combined `pucklogic_trends_score` (blended Layer 1 + Layer 2, weighted by season phase)
5. ☐ Updated `/api/trends` endpoint with Layer 2 data and subscription gate (top-10 paywalled for free users)
6. ☐ Layer 2b: Optional Bayesian recalibration module — ships only if historical data supports calibration (see Section 6)
7. ☐ Additional scrapers: DailyFaceoff PP unit tracking, NHL.com injury feed, NST line combo tracking
8. ☐ Test coverage (pytest, mocked scrapers and DB)

---

## 1. Layer 2 Signals Architecture

### 1.1 Signal Overview

Layer 2 tracks 8 leading indicators over a **14-day rolling window**. Each signal produces a Z-score: `(player's 14-day rolling avg − player's season baseline) / season σ`.

| Signal | Source | What it detects | DB column(s) |
|--------|--------|-----------------|--------------|
| TOI change (5v5, PP, SH) | NHL.com API | More ice = more opportunity | `toi_per_game` delta |
| PP unit movement (PP1 ↔ PP2) | DailyFaceoff | PP1 vs PP2 is a large fantasy multiplier | `pp_unit` |
| Shots/game trend | NST, MoneyPuck | Shot volume leads goal scoring | `sog_per_game` delta |
| xGF% shift | MoneyPuck | Chance quality improving before goals appear | `xgf_pct` delta |
| Corsi rel% shift | NST | Deployment and usage improving | `cf_pct` delta |
| Line combo changes | DailyFaceoff | Promoted to top-6 → instant value bump | `line_position` |
| Shooting % vs career mean | MoneyPuck | Unlucky player due for positive regression | `shooting_pct` vs career avg |
| Return from injury | NHL.com injury feed | Re-insertion into a top line | `injury_reports.status` |

### 1.2 Signal Weights

```python
SIGNAL_WEIGHTS = {
    "toi_change":              0.25,
    "pp_unit_movement":        0.20,
    "shots_trend":             0.15,
    "xgf_shift":               0.15,
    "corsi_shift":             0.10,
    "line_combo_change":       0.10,
    "shooting_pct_regression": 0.05,
}
# Note: return_from_injury is handled as a binary multiplier (+10 bonus to momentum),
# not a weighted signal — it applies regardless of Z-score direction.
```

---

## 2. Z-Score Engine

### 2.1 `Layer2ScoringService`

**Location:** `apps/api/src/services/layer2_scoring.py`

```python
import math


class Layer2ScoringService:
    WINDOW_DAYS = 14

    SIGNAL_WEIGHTS = {
        "toi_change":              0.25,
        "pp_unit_movement":        0.20,
        "shots_trend":             0.15,
        "xgf_shift":               0.15,
        "corsi_shift":             0.10,
        "line_combo_change":       0.10,
        "shooting_pct_regression": 0.05,
    }

    def compute_z_score(
        self,
        player_id: str,
        metric: str,
        rolling_value: float,
        season_baseline: float,
        season_sigma: float,
    ) -> float:
        """Z = (14-day rolling avg − season baseline) / season σ.
        Returns 0.0 when sigma is zero (no variance yet in the season).
        """
        if season_sigma == 0:
            return 0.0
        return (rolling_value - season_baseline) / season_sigma

    def compute_trending_up_score(self, signal_z_scores: dict[str, float]) -> float:
        """Weighted sum of positive Z-scores, sigmoid-normalized to 0–100."""
        raw = sum(
            self.SIGNAL_WEIGHTS.get(signal, 0) * z
            for signal, z in signal_z_scores.items()
            if z > 0
        )
        # Sigmoid normalization: maps (-∞, +∞) → (0, 100)
        return 100 / (1 + math.exp(-raw))

    def compute_trending_down_score(self, signal_z_scores: dict[str, float]) -> float:
        """Inverse weighting for regression signals → 0–100 scale."""
        raw = sum(
            self.SIGNAL_WEIGHTS.get(signal, 0) * abs(z)
            for signal, z in signal_z_scores.items()
            if z < 0
        )
        return 100 / (1 + math.exp(-raw))

    def compute_momentum_score(
        self,
        trending_up: float,
        trending_down: float,
        return_from_injury: bool = False,
    ) -> float:
        """Momentum = trending_up − trending_down, normalized to 0–100 centered at 50.
        return_from_injury applies a +10 bonus (capped at 100).
        """
        momentum = trending_up - trending_down
        if return_from_injury:
            momentum = min(100, momentum + 10)
        return max(0, min(100, momentum + 50))

    def compute_combined_score(
        self,
        breakout_score: float,   # Layer 1 output (0–1)
        momentum_score: float,   # Layer 2 output (0–100)
        is_preseason: bool,
    ) -> float:
        """Blended PuckLogic Trends Score (0–100).

        Pre-season (Aug–Sep): 80% Layer 1 / 20% Layer 2
            → Layer 1 dominates before in-season data accumulates.
        In-season (Oct–Apr): 30% Layer 1 / 70% Layer 2
            → Layer 2 Z-scores carry the signal once the season is underway.
        """
        l1_weight = 0.80 if is_preseason else 0.30
        l2_weight = 0.20 if is_preseason else 0.70
        # Normalize breakout_score (0–1) to 0–100 before blending
        return (l1_weight * breakout_score * 100) + (l2_weight * momentum_score)
```

### 2.2 Season Phase Detection

```python
from datetime import date


def is_preseason(season: str) -> bool:
    """Returns True if today is in the pre-season window (Aug–Sep).
    Season string format: '2026-27'.
    """
    today = date.today()
    month = today.month
    return month in (8, 9)
```

---

## 3. Nightly Celery Job

### 3.1 Task Definition

**Location:** `apps/api/src/jobs/tasks/layer2_rescore.py`

```python
from celery import shared_task
from src.services.layer2_scoring import Layer2ScoringService, is_preseason
from src.repositories.players import fetch_active_skaters
from src.repositories.stats import fetch_rolling_stats, fetch_season_baseline
from src.repositories.trends import upsert_player_trends
from src.repositories.injuries import check_return_from_injury


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def nightly_layer2_rescore(self, season: str) -> dict:
    """Nightly job (runs ~4 AM UTC / 11 PM ET, after all game data is ingested).

    Steps:
        1. Fetch all active skaters for the season.
        2. For each player, fetch 14-day rolling stats and season baseline.
        3. Compute Z-scores for each of the 7 weighted signals.
        4. Compute trending_up, trending_down, and momentum scores.
        5. Apply return_from_injury binary multiplier.
        6. Compute blended pucklogic_trends_score (Layer 1 + Layer 2).
        7. Upsert results to player_trends with signals_json for UI explainability.
    """
    try:
        service = Layer2ScoringService()
        players = fetch_active_skaters(season)
        preseason = is_preseason(season)
        rescored = 0

        for player in players:
            rolling = fetch_rolling_stats(player.id, days=service.WINDOW_DAYS)
            baseline = fetch_season_baseline(player.id, season)

            # Compute per-signal Z-scores
            z_scores = {
                signal: service.compute_z_score(
                    player.id,
                    signal,
                    rolling[signal],
                    baseline[signal],
                    baseline[f"{signal}_sigma"],
                )
                for signal in service.SIGNAL_WEIGHTS
            }

            trending_up = service.compute_trending_up_score(z_scores)
            trending_down = service.compute_trending_down_score(z_scores)
            is_injured_return = check_return_from_injury(player.id)
            momentum = service.compute_momentum_score(
                trending_up, trending_down, is_injured_return
            )
            combined = service.compute_combined_score(
                player.breakout_score or 0.5,
                momentum,
                is_preseason=preseason,
            )

            upsert_player_trends(player.id, season, {
                "trending_up_score":    trending_up,
                "trending_down_score":  trending_down,
                "momentum_score":       momentum,
                "signals_json":         z_scores,
                "window_days":          service.WINDOW_DAYS,
                "pucklogic_trends_score": combined,
            })
            rescored += 1

        return {"rescored": rescored, "season": season}

    except Exception as exc:
        raise self.retry(exc=exc)
```

### 3.2 Celery Beat Schedule

**Location:** `apps/api/src/jobs/celery_config.py`

```python
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    "nightly-layer2-rescore": {
        "task": "src.jobs.tasks.layer2_rescore.nightly_layer2_rescore",
        "schedule": crontab(hour=4, minute=0),   # 4 AM UTC = 11 PM ET
        "kwargs": {"season": "2026-27"},
    },
}
```

The schedule runs after the nightly stats ingestion jobs (NHL.com, MoneyPuck, NST) so fresh data is already in the database when re-scoring begins.

---

## 4. Database Schema Updates

### 4.1 `player_trends` — New Layer 2 Columns

The `player_trends` table (stubbed in Phase 1) gains five new columns for Layer 2 output:

```sql
ALTER TABLE player_trends
  ADD COLUMN IF NOT EXISTS trending_up_score     NUMERIC(5, 2),     -- 0–100
  ADD COLUMN IF NOT EXISTS trending_down_score   NUMERIC(5, 2),     -- 0–100
  ADD COLUMN IF NOT EXISTS momentum_score        NUMERIC(5, 2),     -- 0–100
  ADD COLUMN IF NOT EXISTS signals_json          JSONB,             -- per-signal Z-scores
  ADD COLUMN IF NOT EXISTS window_days           INTEGER DEFAULT 14,
  ADD COLUMN IF NOT EXISTS pucklogic_trends_score NUMERIC(5, 2);    -- blended 0–100
```

Full `player_trends` column inventory after v2.0:

| Column | Type | Layer | Description |
|--------|------|-------|-------------|
| `player_id` | UUID FK | — | References `players.id` |
| `season` | TEXT | — | e.g. `'2026-27'` |
| `breakout_score` | NUMERIC(4,3) | Layer 1 | 0–1 probability of breakout |
| `regression_risk` | NUMERIC(4,3) | Layer 1 | 0–1 probability of regression |
| `confidence` | TEXT | Layer 1 | `'HIGH'` / `'MEDIUM'` / `'LOW'` |
| `trending_up_score` | NUMERIC(5,2) | Layer 2 | 0–100, sigmoid-normalized |
| `trending_down_score` | NUMERIC(5,2) | Layer 2 | 0–100, sigmoid-normalized |
| `momentum_score` | NUMERIC(5,2) | Layer 2 | 0–100, centered at 50 |
| `signals_json` | JSONB | Layer 2 | Per-signal Z-scores (for UI explainability) |
| `window_days` | INTEGER | Layer 2 | Rolling window size (always 14) |
| `pucklogic_trends_score` | NUMERIC(5,2) | Combined | Blended Layer 1 + Layer 2, 0–100 |
| `updated_at` | TIMESTAMPTZ | — | Set by nightly Celery job |

### 4.2 `injury_reports` Table — Fully Activated

The `injury_reports` table was stubbed in Phase 1. v2.0 fully populates it via the NHL.com injury scraper.

```sql
-- Phase 1 stub — now fully in use (v2.0)
CREATE TABLE injury_reports (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id    UUID REFERENCES players(id) ON DELETE CASCADE,
  status       TEXT CHECK (status IN (
                 'healthy', 'day_to_day', 'injured_reserve', 'long_term_ir'
               )),
  description  TEXT,
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id)   -- one row per player, upserted daily
);
```

When a player transitions from `injured_reserve` or `long_term_ir` → `healthy`, the `check_return_from_injury()` function returns `True` for a 7-day window, activating the binary multiplier in `compute_momentum_score()`.

---

## 5. New Scrapers (v2.0)

### 5.1 DailyFaceoff PP Unit Tracker

**Location:** `apps/api/src/scrapers/dailyfaceoff.py`

Scrapes `dailyfaceoff.com/nhl/depth-charts` (HTML, BeautifulSoup) to determine which power play unit (PP1 or PP2) each player is on.

| Attribute | Detail |
|-----------|--------|
| Target URL | `https://www.dailyfaceoff.com/nhl/depth-charts` |
| Method | HTML scraper (BeautifulSoup; Playwright fallback if JS-rendered) |
| Frequency | Daily (pre-game) — GitHub Actions cron |
| Output | Upserts `pp_unit` into `player_stats` |
| Signal produced | `pp_unit_movement` Z-score |

Key logic:
- Parse each team's depth chart section
- Assign `pp_unit = 1` (PP1) or `pp_unit = 2` (PP2) or `null` (not on PP)
- Compare to previous day's value — a change triggers a non-zero Z-score for `pp_unit_movement`
- Also captures `line_position` (line 1–4) for the `line_combo_change` signal

```python
class DailyFaceoffScraper:
    BASE_URL = "https://www.dailyfaceoff.com/nhl/depth-charts"
    RATE_LIMIT_SECONDS = 2.0   # be respectful — check robots.txt

    def fetch_depth_charts(self) -> list[dict]:
        """Returns list of {player_id, team, pp_unit, line_position}."""
        ...

    def detect_pp_unit_changes(
        self, current: list[dict], previous: list[dict]
    ) -> list[dict]:
        """Compares current and previous day's PP assignments.
        Returns players whose pp_unit changed.
        """
        ...
```

### 5.2 NHL.com Injury Feed

**Location:** `apps/api/src/scrapers/nhl_injuries.py`

Polls the NHL injury reports endpoint daily to keep `injury_reports` current.

| Attribute | Detail |
|-----------|--------|
| Target | NHL.com API injury endpoint |
| Method | Official API (JSON) |
| Frequency | Daily |
| Output | Upserts `injury_reports` table |
| Signal produced | `return_from_injury` binary multiplier |

```python
class NHLInjuryScraper:
    BASE_URL = "https://api-web.nhle.com/v1"

    def fetch_injury_report(self) -> list[dict]:
        """Returns [{player_id, status, description, updated_at}]."""
        ...

    def upsert_injury_reports(self, reports: list[dict]) -> None:
        """Upserts into injury_reports table. One row per player."""
        ...
```

### 5.3 Scraper Cron Schedule (GitHub Actions)

```yaml
# .github/workflows/scrapers-v2.yml
on:
  schedule:
    - cron: "0 12 * * *"   # noon UTC daily — before nightly Celery re-scoring

jobs:
  scrape-dailyfaceoff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m src.scrapers.dailyfaceoff

  scrape-nhl-injuries:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m src.scrapers.nhl_injuries
```

Always respect `robots.txt` for all scrapers. Add exponential backoff on HTTP errors.

---

## 6. Updated `/api/trends` Endpoint

### 6.1 Router Update

**Location:** `apps/api/src/routers/trends.py`

```python
from fastapi import APIRouter, Depends
from src.auth.dependencies import get_current_user
from src.db.dependencies import get_db
from src.repositories.trends import fetch_all_trends
from src.repositories.subscriptions import get_user_subscription
from src.models.user import User

router = APIRouter()


@router.get("/api/trends")
async def get_trends(
    season: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db),
):
    """Returns all player trends for a given season.

    Subscription gate (v2.0):
        - Free tier: top-10 players by pucklogic_trends_score have signals_json
          stripped and paywalled=True. Breakout/regression scores still returned.
        - Pro tier: full access to all scores and signals_json explainability.
    """
    trends = await fetch_all_trends(season, db)
    subscription = await get_user_subscription(current_user.id, db)

    if subscription.plan == "free":
        # Sort descending by combined score to identify the top 10
        trends.sort(
            key=lambda t: t.pucklogic_trends_score or 0,
            reverse=True,
        )
        for trend in trends[:10]:
            trend.signals_json = None    # hide per-signal Z-scores
            trend.paywalled = True

    return {
        "trends": trends,
        "layer": "1+2",
        "season": season,
    }
```

### 6.2 Response Shape (v2.0 additions)

The existing `PlayerTrendResponse` schema is extended:

```python
class PlayerTrendResponse(BaseModel):
    # Layer 1 fields (Phase 3 — unchanged)
    player_id: str
    name: str
    position: str
    age: int
    team: str
    breakout_score: float           # 0–1
    regression_risk: float          # 0–1
    confidence: str                 # 'HIGH' | 'MEDIUM' | 'LOW'
    shap_top3: list[ShapContrib]
    fantasy_pts: float
    vorp: float

    # Layer 2 additions (v2.0)
    trending_up_score: float | None    # 0–100; null before v2.0 launch
    trending_down_score: float | None  # 0–100
    momentum_score: float | None       # 0–100, centered at 50
    signals_json: dict | None          # null for free-tier top-10 (paywalled)
    window_days: int                   # always 14
    pucklogic_trends_score: float | None  # blended 0–100

    # Gate flag
    paywalled: bool = False
```

---

## 7. Layer 2b: Bayesian Recalibration (Optional Module)

> **Important:** Layer 2b is optional and will only ship with v2.0 if at least one full season of historical `(trending_up_score, actual_pts_delta)` pairs are available for training. Do not ship this module if calibration data is insufficient — raw sigmoid scores are the fallback.

### 7.1 Purpose

Converts raw sigmoid-normalized Z-scores (`trending_up_score`) into **calibrated probabilities** — e.g., "this score historically corresponds to a 72% chance of outperforming over the next 14 days." Uses Platt scaling (logistic regression trained on historical outcomes).

### 7.2 `BayesianRecalibrator`

**Location:** `apps/api/src/services/layer2b_calibration.py`

```python
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV


class BayesianRecalibrator:
    """Optional post-processing step.

    Converts trending_up_score → P(outperform_next_14_days).

    Training data requirements:
        - At least one full NHL season of (trending_up_score, outperformed_bool) pairs.
        - 'outperformed' = player scored ≥ 20% above their 14-day baseline in the
          subsequent 14-day window.

    Model: sklearn LogisticRegression (Platt scaling).
    Artifact: serialized to models/layer2b_calibration.joblib.

    DO NOT deploy this module without validating calibration curves
    (reliability diagram) on a held-out season.
    """

    MODEL_PATH = "models/layer2b_calibration.joblib"

    def __init__(self):
        self.model: LogisticRegression | None = None
        self._load_if_exists()

    def _load_if_exists(self) -> None:
        try:
            self.model = joblib.load(self.MODEL_PATH)
        except FileNotFoundError:
            self.model = None   # graceful degradation — raw scores used instead

    def is_available(self) -> bool:
        return self.model is not None

    def calibrate(self, raw_score: float) -> float:
        """Returns P(outperform | trending_up_score) in [0, 1].
        Raises RuntimeError if model is not available.
        """
        if not self.is_available():
            raise RuntimeError("Calibration model not trained — use raw scores.")
        return float(self.model.predict_proba([[raw_score]])[0][1])

    def batch_calibrate(self, scores: list[float]) -> list[float]:
        if not self.is_available():
            raise RuntimeError("Calibration model not trained.")
        arr = np.array(scores).reshape(-1, 1)
        return self.model.predict_proba(arr)[:, 1].tolist()

    @classmethod
    def train(
        cls,
        X: list[float],       # historical trending_up_scores
        y: list[int],         # 1 = outperformed, 0 = did not
    ) -> "BayesianRecalibrator":
        """Train and serialize the calibration model.
        Call from a one-off training script — not from the Celery job.
        """
        base = LogisticRegression()
        calibrated = CalibratedClassifierCV(base, method="sigmoid", cv=5)
        calibrated.fit(np.array(X).reshape(-1, 1), y)
        joblib.dump(calibrated, cls.MODEL_PATH)
        instance = cls()
        instance.model = calibrated
        return instance
```

When `BayesianRecalibrator.is_available()` returns `False`, the API falls back to returning raw `trending_up_score` values. The `player_trends.confidence` column is set to `'LOW'` for uncalibrated scores.

---

## 8. Testing

### 8.1 Z-Score Engine Tests

**Location:** `apps/api/tests/services/test_layer2_scoring.py`

| Test | What it verifies |
|------|-----------------|
| `test_z_score_positive_when_above_baseline` | Z > 0 when rolling value exceeds season baseline |
| `test_z_score_negative_when_below_baseline` | Z < 0 when rolling value is below season baseline |
| `test_z_score_zero_when_no_variance` | Returns 0.0 gracefully when season_sigma = 0 |
| `test_trending_up_bounded_0_to_100` | Sigmoid output is always in [0, 100] range |
| `test_trending_down_bounded_0_to_100` | Same for trending_down |
| `test_momentum_injury_bonus` | `return_from_injury=True` adds +10, capped at 100 |
| `test_momentum_no_bonus_without_injury` | No bonus applied when `return_from_injury=False` |
| `test_combined_score_preseason_weights` | 80% Layer 1 / 20% Layer 2 split verified |
| `test_combined_score_inseason_weights` | 30% Layer 1 / 70% Layer 2 split verified |
| `test_combined_score_bounded_0_to_100` | Blended score never exceeds 0–100 range |

```python
import math
import pytest
from src.services.layer2_scoring import Layer2ScoringService


@pytest.fixture
def service():
    return Layer2ScoringService()


def test_z_score_positive_when_above_baseline(service):
    z = service.compute_z_score("p1", "toi_change", rolling_value=22.5, season_baseline=20.0, season_sigma=1.5)
    assert z > 0


def test_z_score_zero_when_no_variance(service):
    z = service.compute_z_score("p1", "toi_change", rolling_value=22.5, season_baseline=20.0, season_sigma=0)
    assert z == 0.0


def test_trending_up_bounded_0_to_100(service):
    # Extreme positive Z-scores
    scores = {"toi_change": 5.0, "pp_unit_movement": 4.0, "shots_trend": 3.0}
    result = service.compute_trending_up_score(scores)
    assert 0 <= result <= 100


def test_momentum_injury_bonus(service):
    score = service.compute_momentum_score(trending_up=60.0, trending_down=30.0, return_from_injury=True)
    score_without = service.compute_momentum_score(trending_up=60.0, trending_down=30.0, return_from_injury=False)
    assert score == min(100, score_without + 10) or score == 100


def test_combined_score_preseason_weights(service):
    # breakout_score=1.0 (normalized to 100), momentum=0.0 → should be 80
    result = service.compute_combined_score(breakout_score=1.0, momentum_score=0.0, is_preseason=True)
    assert math.isclose(result, 80.0, rel_tol=1e-5)


def test_combined_score_inseason_weights(service):
    # breakout_score=0.0, momentum=100.0 → should be 70
    result = service.compute_combined_score(breakout_score=0.0, momentum_score=100.0, is_preseason=False)
    assert math.isclose(result, 70.0, rel_tol=1e-5)
```

### 8.2 Celery Job Tests

**Location:** `apps/api/tests/jobs/test_layer2_rescore.py`

- Mock `fetch_active_skaters`, `fetch_rolling_stats`, `fetch_season_baseline`, `check_return_from_injury`, and `upsert_player_trends` with `MagicMock`/`AsyncMock`
- `test_rescore_calls_upsert_for_each_player` — verify `upsert_player_trends` is called once per player
- `test_rescore_returns_correct_count` — task return dict includes `"rescored": N`
- `test_rescore_retries_on_exception` — verify Celery `self.retry()` is called on DB failure

### 8.3 Subscription Gate Tests

**Location:** `apps/api/tests/routers/test_trends_gate.py`

- `test_free_user_top10_signals_json_null` — free user response has `signals_json=null` for players ranked 1–10
- `test_free_user_top10_paywalled_true` — `paywalled=True` for top-10 free-tier rows
- `test_free_user_outside_top10_has_signals` — positions 11+ are not paywalled for free users
- `test_pro_user_gets_full_signals_json` — pro subscription returns full `signals_json` for all players
- All DB calls mocked via `pytest` fixtures in `tests/conftest.py`

---

## 9. Performance Considerations

| Aspect | Target | Strategy |
|--------|--------|----------|
| Nightly rescore job (850 players) | < 5 minutes | Batch DB reads, bulk upsert |
| `/api/trends` response time | < 300ms | Redis cache (6h TTL) on computed trend rows |
| `signals_json` payload size | < 2 KB/player | 7 float values — negligible; gzip on transport |
| Celery retry on failure | 3 retries, 5 min delay | `max_retries=3, default_retry_delay=300` |

---

## 10. Deployment Checklist

- [ ] Supabase migration applied: new `player_trends` columns added
- [ ] `injury_reports` table fully seeded from NHL.com scraper
- [ ] DailyFaceoff scraper GitHub Action enabled and passing
- [ ] NHL.com injury scraper GitHub Action enabled and passing
- [ ] `layer2_rescore` Celery task registered and appearing in Celery worker logs
- [ ] Celery Beat schedule confirmed (4 AM UTC)
- [ ] `/api/trends` endpoint returns `signals_json` for pro users
- [ ] `/api/trends` endpoint strips `signals_json` and sets `paywalled=True` for free-tier top-10
- [ ] Layer 2b calibration model trained and validated (reliability diagram reviewed) — only deploy if data supports
- [ ] All pytest tests green
- [ ] Redis cache confirmed warm after first nightly run

---

## Appendix: Key Files

| File | Purpose |
|------|---------|
| `apps/api/src/services/layer2_scoring.py` | Z-score engine, trending scores, combined score blending |
| `apps/api/src/services/layer2b_calibration.py` | Optional Bayesian recalibration (Platt scaling) |
| `apps/api/src/jobs/tasks/layer2_rescore.py` | Nightly Celery rescore task |
| `apps/api/src/jobs/celery_config.py` | Celery Beat schedule (4 AM UTC) |
| `apps/api/src/scrapers/dailyfaceoff.py` | PP unit + line combo tracker |
| `apps/api/src/scrapers/nhl_injuries.py` | NHL.com injury feed scraper |
| `apps/api/src/routers/trends.py` | Updated `/api/trends` with Layer 2 data + subscription gate |
| `apps/api/tests/services/test_layer2_scoring.py` | Z-score engine unit tests |
| `apps/api/tests/jobs/test_layer2_rescore.py` | Celery job tests (mocked DB) |
| `apps/api/tests/routers/test_trends_gate.py` | Subscription gate integration tests |
| `models/layer2b_calibration.joblib` | Serialized Platt scaling model (generated, not committed) |

---

*See also: `docs/v2-frontend.md` (in-season trends UI) · `docs/phase-3-backend.md` (Layer 1 ML backend)*
