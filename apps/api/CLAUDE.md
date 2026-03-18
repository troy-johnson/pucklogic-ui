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
    players.py       # PlayerRepository — Supabase CRUD for `players`
    projections.py   # ProjectionsRepository — get_by_season(season, platform, user_id)
    sources.py       # SourceRepository — list()
  routers/
    health.py        # GET /health (Phase 1, registered)
    sources.py       # GET /sources (Phase 2, registered)
    rankings.py      # POST /rankings/compute (Phase 2, TODO: register in main.py)
    exports.py       # POST /exports/generate (Phase 2, TODO: register)
    stripe.py        # POST /stripe/create-checkout-session (Phase 2, TODO: register)
    user_kits.py     # CRUD /user-kits (Phase 2, TODO: register)
  services/
    projections.py   # aggregate_projections(), compute_weighted_stats(), apply_scoring_config(), compute_vorp()
    cache.py         # CacheService — Upstash-compatible Redis, 6h TTL
    exports.py       # generate_excel(), generate_pdf()
  scrapers/
    base.py                  # BaseScraper ABC (stat sources: NHL.com, MoneyPuck)
    base_projection.py       # BaseProjectionScraper ABC (projection sources)
    nhl_com.py               # NhlComScraper → player_stats
    moneypuck.py             # MoneyPuckScraper → player_stats
    matching.py              # Player name/ID resolution (rapidfuzz)
  tests/
    conftest.py      # `client` fixture (TestClient wrapping app)
    test_health.py
    repositories/    # test_players.py, test_projections.py, test_sources.py, test_subscriptions.py
    services/        # test_projections.py, test_cache.py, test_exports.py
    routers/         # test_sources.py, test_rankings.py, test_exports.py, test_stripe.py, test_user_kits.py
    scrapers/        # test_base.py, test_base_projection.py, test_nhl_com.py, test_moneypuck.py
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
| `scrapers/projection/` | ⬜ TODO | HashtagHockey, DailyFaceoff, Apples & Ginos, LineupExperts, Yahoo, Fantrax scrapers |
| `scrapers/nst.py` | ⬜ TODO | Natural Stat Trick HTML scraper — writes to `player_stats` |
| `scrapers/matching.py` | ⬜ TODO | Player name/ID resolution via rapidfuzz (Phase 1 backlog) |
| Schedule ingestion job | ⬜ TODO | GitHub Actions: NHL schedule API → `schedule_scores` (off-night counts, min-max normalized) |
| `player_platform_positions` ingestion | ⬜ TODO | Per-platform position eligibility for ESPN, Yahoo, Fantrax |
| Custom upload UI + handler | ⬜ TODO | 2 slots per user, CSV/Excel, column mapping, `sources.user_id` set, triggers cache invalidation |

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
