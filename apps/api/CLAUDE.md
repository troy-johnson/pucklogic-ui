# PuckLogic API — Claude Code Context

FastAPI backend for the PuckLogic fantasy hockey draft kit.
Dev server: `http://localhost:8000` · Docs (dev only): `/docs`

---

## Quick Commands

```bash
# from apps/api/
pip install -e ".[dev]"          # first-time install
uvicorn main:app --reload        # dev server on :8000
pytest                           # run all tests (coverage printed)
ruff check .                     # lint
ruff format .                    # format
```

---

## Directory Layout

```
apps/api/
  core/
    config.py        # Settings (pydantic-settings, reads .env)
    dependencies.py  # FastAPI Depends() helpers — get_source_repository, get_projections_repository, get_cache_service
  models/
    schemas.py       # All Pydantic request/response schemas (Phase 2 complete)
  repositories/
    players.py       # PlayerRepository — list(limit, offset), get(id)
    projections.py   # ProjectionsRepository — get_by_season(season, platform, user_id)
    sources.py       # SourceRepository — list, get, get_by_name, get_by_names, list_custom,
                     #   upsert_custom, delete_custom, count_custom, get_seasons_for_source
    scoring_configs.py  # ScoringConfigRepository — list, get, create, list_presets
    league_profiles.py  # LeagueProfileRepository — list, get, create
    subscriptions.py    # SubscriptionRepository — is_active(user_id)
  routers/
    health.py        # GET /health
    sources.py       # GET /sources · GET /sources/custom · POST /sources/upload · DELETE /sources/{id}
    rankings.py      # POST /rankings/compute — projection aggregation pipeline (auth required)
    scoring_configs.py  # GET /scoring-configs/presets · GET /scoring-configs · POST /scoring-configs
    league_profiles.py  # GET/POST /league-profiles
    exports.py       # POST /exports/generate — PDF/Excel streaming
    stripe.py        # POST /stripe/create-checkout-session · POST /stripe/webhook
    user_kits.py     # GET/POST/DELETE /user-kits
    auth.py          # POST /auth/register,login,logout,refresh · GET /auth/me
    players.py       # GET /players · GET /players/{id}
  services/
    projections.py   # aggregate_projections(), compute_weighted_stats(), apply_scoring_config(), compute_vorp()
    cache.py         # CacheService — Upstash Redis, 6h TTL, SHA-256 cache keys, SCAN invalidation
    exports.py       # generate_excel(), generate_pdf()
    scoring_validation.py  # validate_scoring_config() — PPP/PPG/PPA + SHP/SHG/SHA mutual exclusion
  scrapers/
    base.py                  # BaseScraper ABC — async _check_robots_txt, _get_with_retry
    base_projection.py       # BaseProjectionScraper ABC → player_projections
    nhl_com.py               # NhlComScraper → player_stats
    moneypuck.py             # MoneyPuckScraper → player_stats
    nst.py                   # NstScraper (BeautifulSoup) → player_stats
    matching.py              # PlayerMatcher — exact → alias → rapidfuzz (threshold 85)
    platform_positions.py    # ESPN (auto), Yahoo (OAuth2), Fantrax (stub) → player_platform_positions
    schedule_scores.py       # NHL schedule API → schedule_scores
    projection/
      __init__.py            # Shared helpers: upsert_source, upsert_projection_row, apply_column_map
      hashtag_hockey.py      # HTML scraper; per-game rate × GP conversion
      daily_faceoff.py / dobber.py / apples_ginos.py / lineup_experts.py  # CSV paste/upload
      yahoo.py               # Yahoo Fantasy API (OAuth2)
      fantrax.py             # Fantrax REST API
  tests/
    conftest.py      # `client` fixture (TestClient wrapping app)
    test_health.py
    repositories/    # test_players, test_projections, test_sources, test_scoring_configs,
                     #   test_league_profiles, test_subscriptions
    services/        # test_projections, test_cache, test_exports, test_scoring_validation
    routers/         # test_sources, test_rankings, test_exports, test_stripe, test_user_kits,
                     #   test_scoring_configs, test_league_profiles, test_auth, test_players
    scrapers/        # test_base, test_base_projection, test_nhl_com, test_moneypuck,
                     #   test_platform_positions, test_schedule_scores
                     #   projection/: test_hashtag_hockey, test_daily_faceoff, test_dobber,
                     #                test_apples_ginos, test_lineup_experts, test_yahoo, test_fantrax
  main.py            # FastAPI app, CORS, registered routers
  pyproject.toml     # deps + tool config (ruff, pytest, coverage)
```

---

## Version Scope

| Version | Trends API |
|---------|------------|
| **v1.0 (Phase 3)** | `GET /trends` returns pre-season Layer 1 scores (`breakout_score`, `regression_risk`, `confidence`, SHAP values) from `player_trends`. No paywall gate needed — all scores visible to free users. Feature spec: `docs/feature-engineering-spec.md`. |
| **v2.0 (post-launch)** | Layer 2 in-season engine: nightly Celery job populates `trending_up_score`, `trending_down_score`, `momentum_score`, `signals_json`. Paywall gate strips top-10 rows for free users. Endpoint extended, not replaced. |

Do not build Layer 2 Celery jobs, Z-score computation, or the paywall gate until v2.0 is scoped for implementation.

---

## Phase 2 Status

| Area | Status | Notes |
|------|--------|-------|
| `models/schemas.py` | ✅ Complete | All Phase 2 schemas defined; `RankingsComputeRequest` uses `source_weights`, `scoring_config_id`, `platform`, `league_profile_id`; `UserKitCreate`/`UserKitOut` are source-weight presets only |
| `repositories/` | ✅ Complete | players (`list(limit, offset)` — paginated via `.range()`), projections (`get_by_season(season, platform, user_id)`), sources, subscriptions |
| `services/projections.py` | ✅ Complete | `aggregate_projections`, `compute_weighted_stats`, `apply_scoring_config`, `compute_vorp` |
| `services/cache.py` | ✅ Complete | `CacheService` with Upstash Redis, graceful no-op when unconfigured; cache key = `rankings:{season}:{sha256(source_weights+scoring_config_id+platform+league_profile_id)}` |
| `services/exports.py` | ✅ Complete | `generate_excel` (2 sheets: Full Rankings + Best Available), `generate_pdf` (Print & Draft) |
| `routers/sources.py` | ✅ Complete | GET /sources |
| `core/dependencies.py` | ✅ Complete | `get_db`, `get_cache_service`, `get_projections_repository`, `get_source_repository`, `get_subscription_repository`, `get_current_user` |
| `routers/rankings.py` | ✅ Complete | POST /rankings/compute — auth required, Redis cache, 6h TTL, stat-projection-based pipeline |
| `routers/exports.py` | ✅ Complete | POST /exports/generate — PDF + Excel streaming response |
| `routers/stripe.py` | ✅ Complete | POST /stripe/create-checkout-session + /webhook (signature-verified) |
| `routers/user_kits.py` | ✅ Complete | GET/POST/DELETE /user-kits — owner-scoped source-weight presets |
| `main.py` router includes | ✅ Complete | All 6 routers registered |
| `core/config.py` new fields | ✅ Complete | `redis_url`, `stripe_secret_key`, `stripe_webhook_secret`, `stripe_price_id`, `frontend_url`, `current_season` |
| `pyproject.toml` new deps | ✅ Complete | redis, stripe, openpyxl, weasyprint, httpx |
| Backend tests | ✅ Complete | Full suite: services/ (projections, cache, exports), routers/ (all 6), repositories/ |

### Phase 2 — Still Needed

| Area | Status | Notes |
|------|--------|-------|
| `routers/auth.py` | ✅ Complete | POST /auth/register,login,logout,refresh + GET /auth/me; thin Supabase Auth wrapper; email-confirmation 202 path; admin.sign_out for token revocation |
| `routers/players.py` | ✅ Complete | GET /players, GET /players/{id} |
| `scrapers/projection/yahoo.py` | ✅ Complete | Yahoo Fantasy API (OAuth2); paginated via `game.player_stats()` |
| `scrapers/projection/fantrax.py` | ✅ Complete | Fantrax REST API; inherits `BaseScraper` + `BaseProjectionScraper` |
| `scrapers/nst.py` | ✅ Complete | Natural Stat Trick HTML scraper — writes to `player_stats` |
| `scrapers/matching.py` | ✅ Complete | Player name/ID resolution via rapidfuzz (Phase 1 backlog) |
| `scrapers/schedule_scores.py` | ✅ Complete | GitHub Actions: NHL schedule API → `schedule_scores` (`OFF_NIGHT_THRESHOLD=16`) |
| `scrapers/platform_positions.py` | ✅ Complete | Per-platform position eligibility for ESPN (auto-scrape), Yahoo (OAuth2), Fantrax (stub) |
| Custom upload backend | ✅ Complete | `POST /sources/upload`, `GET /sources/custom`, `DELETE /sources/{id}`; 2-slot limit, TOCTOU guard, paywalled-source gate, stale-projection cleanup, cache invalidation; 53 tests green (PR #21) |
| Custom upload frontend UI | ⬜ Deferred | File drop zone, column mapping step, unmatched player review — deferred until frontend dashboard work begins |

---

## Phase 3 Status

### Phase 3a — Schema Migration + Trends API Schemas (feat/3a-migrations, PR #23)

| Area | Status | Notes |
|------|--------|-------|
| `supabase/migrations/003_phase3_ml_features.sql` | ✅ Complete | 27 new columns on `player_stats` (Tier 1–3 features + flag columns + `sh_pct_career_avg`); 5 new columns on `player_trends` (`breakout_signals`, `regression_signals`, `shap_top3`, `projection_pts`, `projection_tier`); composite season-first indexes; named CHECK constraints via idempotent DO blocks |
| `models/schemas.py` Phase 3 section | ✅ Complete | `ShapValues`, `TrendedPlayer`, `TrendsResponse`; `ProjectionTier`/`SkaterPosition` Literals; `StrictBool` signals; `Field(ge=0, le=1)` probability scores; `@computed_field` for `player_count`; `has_trends` + `updated_at` consistency enforced by model_validator |
| `tests/models/test_schemas.py` | ✅ Complete | 26 tests covering all new schemas; boundary values, Literal enforcement, StrictBool rejection, round-trip serialization |

### Phase 3b — Smoke Tests (✅ Complete, PR #25)

| Area | Status | Notes |
|------|--------|-------|
| `tests/smoke/` — per-scraper live integration tests | ✅ Complete | NHL.com, MoneyPuck, Hockey Reference, NST, NHL EDGE; 24 passed, 12 skipped (NST Cloudflare) |
| `scripts/run_smoke_tests.sh` | ✅ Complete | venv detection, dynamic JWT from `supabase status`, `--override-ini` to bypass coverage flags |
| Scraper bug fixes | ✅ Complete | HR HTML attrs (`id="player_stats"`, `name_display`, `games`); MoneyPuck `5on5`; NHL EDGE 500 handling; NST 403 handling on primary + situation fetches |
| Migration fix (`002_projection_aggregation.sql`) | ✅ Complete | Moved `sources` column additions before `player_projections` RLS policy that referenced `sources.user_id` |

### Phase 3c — Feature Engineering Pipeline (✅ Complete, PR #26)

| Area | Status | Notes |
|------|--------|-------|
| Hockey Reference (`scrapers/hockey_reference.py`) | ✅ Complete | `sh_pct_career_avg` (Tier 1), `nhl_experience` (Tier 2); `scrape_history()` for backfill; `scrape()` for annual updates; 25 tests |
| Elite Prospects (`scrapers/elite_prospects.py`) | ✅ Complete | `elc_flag`, `contract_year_flag` (Tier 3); requires `ELITE_PROSPECTS_API_KEY` secret; field names are approximate — verify against live API |
| NHL EDGE (`scrapers/nhl_edge.py`) | ✅ Complete | `speed_bursts_22`, `top_speed` (Tier 3, optional); free NHL API; field names approximate — verify against live API |
| Evolving Hockey (`gar`, `xgar`) | 🔁 Manual | No scraper — $5/month subscription; ingest via `POST /sources/upload`; per spec Decisions §2 |
| `repositories/player_stats.py` | ✅ Complete | `PlayerStatsRepository.get_seasons_grouped()` — 3-season window, players join flattened, newest-first; 9 tests |
| `services/feature_engineering.py` | ✅ Complete | Marcel 3yr weighted rates, breakout/regression signals (8+7), tier assignment; stale-season fallback with warning; 96 tests |

**Phase 3c backlog (resolve before Phase 3d):** `stale_season` + `position_type` output flags + spec drift fix for `a2_pct_of_assists` (Notion P2). All scrapers are skater-only so goalie contamination is not a current risk.

### Phase 3d — Model Training + Inference API (✅ Complete, PR #28, 2026-03-24)

| Area | Status | Notes |
|------|--------|-------|
| `apps/api/ml/` module | ✅ Complete | `train.py`, `loader.py`, `evaluate.py`, `shap_compute.py` |
| XGBoost/LightGBM training pipeline | ✅ Complete | XGBoost primary; LightGBM challenger; 5-fold time-series CV; Optuna 50 trials; holdout 2023–2024 excluded from CV, included in final retrain |
| SHAP value computation | ✅ Complete | `shap.TreeExplainer`; top-3 by abs(shap_value) stored as JSONB in `player_trends.shap_values` |
| `player_trends` upserts | ✅ Complete | `breakout_score`, `regression_risk`, `confidence`, `shap_values`, `updated_at`; upsert with `file_options={"upsert": "true"}` |
| Yearly retraining GitHub Action | ✅ Complete | `retrain-trends.yml` — triggers Aug 1 annually + manual dispatch; steps: pip install → scrape → train |
| `repositories/trends.py` | ✅ Complete | `TrendsRepository.get_trends(season)` — LEFT JOIN players + player_trends |
| `routers/trends.py` — GET /trends | ✅ Complete | Returns `TrendsResponse`; 503 if model not loaded; `has_trends=False` for pre-training; no paywall in v1.0 |
| FastAPI lifespan hook | ✅ Complete | `loader.py` called at startup; raises `ModelNotAvailableError` on Storage failure; dev cache at `~/.pucklogic/models/data_season/` |

---

### Phase 2 — Scrapers Complete (feat/phase2-projection-scrapers)

| Area | Status | Notes |
|------|--------|-------|
| `scrapers/matching.py` | ✅ Complete | `PlayerMatcher` — exact → alias → rapidfuzz (token_sort_ratio, threshold 85) |
| `scrapers/projection/__init__.py` | ✅ Complete | Shared helpers: `upsert_source`, `upsert_projection_row`, `fetch_players_and_aliases`, `log_unmatched`, `update_last_successful_scrape`, `apply_column_map` |
| `scrapers/projection/hashtag_hockey.py` | ✅ Complete | HTML scraper; per-game rate × GP conversion (can't use `apply_column_map` — documented in file) |
| `scrapers/projection/daily_faceoff.py` | ✅ Complete | CSV paste/upload mode |
| `scrapers/projection/dobber.py` | ✅ Complete | CSV paste/upload mode (paywalled — no HTTP) |
| `scrapers/projection/apples_ginos.py` | ✅ Complete | CSV paste/upload mode |
| `scrapers/projection/lineup_experts.py` | ✅ Complete | CSV paste/upload mode |
| `scrapers/nst.py` | ✅ Complete | HTML scraper (BeautifulSoup); writes to `player_stats` |
| GitHub Actions cron | ✅ Complete | `.github/workflows/scrape-projections.yml` — weekly Monday 6am UTC, all 5 scrapers + NST |

---

## Aggregation Pipeline (POST /rankings/compute)

```
POST /rankings/compute:
  Request: { season, source_weights, scoring_config_id, platform, league_profile_id? }

  1. Validate: at least one source_weight > 0; if league_profile_id provided, verify owner
  2. Check cache: CacheService.get(rankings:{season}:{digest})  →  cache hit: return cached=True
  3. Cache miss:
       rows = ProjectionsRepository.get_by_season(season, platform, current_user.id)
         # Filters sources to: user_id IS NULL OR user_id = current_user.id
       weighted_stats = compute_weighted_stats(rows, source_weights)
         # Per stat: SUM(stat × weight) / SUM(weights for sources with this stat)
         # Nulls excluded per-stat; result is null only if no source projected that stat
       fantasy_points = apply_scoring_config(weighted_stats, scoring_config)
         # SUM(stat × scoring_config.stat_weights[stat]); null stats contribute 0
       vorp = compute_vorp(players, league_profile)  # null if no league_profile_id
         # Replacement level = Nth player per position (N = num_teams × position_slots + 1)
         # Position group = players.position (NHL.com canonical); negative VORP allowed
       schedule_scores = fetch from schedule_scores table (null if not yet populated)
       ranked = sort by fantasy_points descending (null fantasy_points sort last)
       CacheService.set(key, ranked, ttl=6h)
  4. Return RankingsComputeResponse with per-player: composite_rank, projected_fantasy_points,
       vorp, schedule_score, off_night_games, source_count, projected_stats (full stat object)

  Cache invalidation: new source ingest → cache.invalidate_rankings(season)
    pattern-deletes all keys matching rankings:{season}:*
```

Missing-source grace: nulls are excluded per-stat. A source projecting goals but not hits
contributes to the goals average only. A stat is null in output only if no source projected it.

---

## Key Schemas (`models/schemas.py`)

| Schema | Used by |
|--------|---------|
| `SourceOut` | GET /sources |
| `RankingsComputeRequest` | POST /rankings/compute — fields: `season`, `source_weights` (renamed from `weights`), `scoring_config_id`, `platform`, `league_profile_id` (optional) |
| `RankingsComputeResponse` | POST /rankings/compute |
| `RankedPlayer` | nested in RankingsComputeResponse.rankings — includes `projected_fantasy_points`, `vorp`, `schedule_score`, `off_night_games`, `source_count`, `projected_stats` |
| `ExportRequest` | POST /exports/generate — same new fields as RankingsComputeRequest |
| `ExportJobResponse` | POST /exports/generate |
| `CheckoutSessionRequest` / `CheckoutSessionResponse` | POST /stripe/create-checkout-session |
| `UserKitCreate` / `UserKitOut` | POST/GET /user-kits — source-weight presets only (no league config) |
| `LeagueProfileCreate` / `LeagueProfileOut` | POST/GET /league-profiles — platform, num_teams, roster_slots, scoring_config_id |
| `ShapValues` | nested in `TrendedPlayer.shap_values` — per-feature SHAP contributions; model_validator rejects both-empty dicts |
| `TrendedPlayer` | nested in `TrendsResponse.players` — ML scores, signals, SHAP top-3; `SkaterPosition` Literal, `ProjectionTier` Literal, `StrictBool` signals, `Field(ge=0, le=1)` scores |
| `TrendsResponse` | GET /trends — `season`, `has_trends`, `updated_at` (None if no trends yet), `players`, `player_count` (computed); model_validator enforces `updated_at` required when `has_trends=True` |

---

## Environment Variables (`.env`)

```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=
REDIS_URL=                    # Upstash Redis REST URL (Phase 2)
STRIPE_SECRET_KEY=            # sk_test_... (Phase 2)
STRIPE_WEBHOOK_SECRET=        # whsec_... (Phase 2)
STRIPE_PRICE_ID=              # price_... (Phase 2)
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
CURRENT_SEASON=2026-27           # e.g. 2026-27 — used by ml.train and GET /trends default
```

Never commit `.env`. It is gitignored.

---

## TDD Rules

1. **Write the test first.** Every new function ships with a test.
2. Mocks over real I/O — `MagicMock` / `pytest-mock`; never hit real DB, Redis, or Stripe.
3. Use `TYPE_CHECKING` guards on heavy imports (`supabase.Client`) to keep test env portable.
4. Mirror source tree under `tests/` — e.g. `services/test_rankings.py`.
5. All tests must be green (`pytest`) before committing.

### Fixture pattern (conftest.py)

```python
@pytest.fixture
def client() -> TestClient:
    return TestClient(app)          # use for router integration tests
```

For service/repo unit tests, construct the class directly and inject `MagicMock` dependencies.

---

## Dependency Injection Pattern

Routers import helpers from `core/dependencies.py`:

```python
from core.dependencies import get_source_repository, get_rankings_repository, get_cache_service

@router.post("", response_model=RankingsComputeResponse)
async def compute_rankings(
    req: RankingsComputeRequest,
    repo: RankingsRepository = Depends(get_rankings_repository),
    cache: CacheService = Depends(get_cache_service),
) -> RankingsComputeResponse:
    ...
```

---

## Coding Conventions

- Python 3.11+; use `from __future__ import annotations` in all modules.
- Pydantic v2 — `BaseModel`, `Field`, `model_config`.
- Async route handlers are preferred; sync is acceptable for CPU-bound code.
- `ruff` enforces E, F, I (isort), UP (pyupgrade) rules; run before committing.
- No `print()` statements — use Python `logging` if debug output is needed.

## MCP Tools

Always use Context7 MCP when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask.
