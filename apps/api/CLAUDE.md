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
    dependencies.py  # FastAPI Depends() helpers — get_source_repository, get_rankings_repository, get_cache_service
  models/
    schemas.py       # All Pydantic request/response schemas (Phase 2 complete)
  repositories/
    players.py       # PlayerRepository — Supabase CRUD for `players`
    rankings.py      # RankingsRepository — get_by_season()
    sources.py       # SourceRepository — list()
  routers/
    health.py        # GET /health (Phase 1, registered)
    sources.py       # GET /sources (Phase 2, registered)
    rankings.py      # POST /rankings/compute (Phase 2, TODO: register in main.py)
    exports.py       # POST /exports/generate (Phase 2, TODO: register)
    stripe.py        # POST /stripe/create-checkout-session (Phase 2, TODO: register)
    user_kits.py     # CRUD /user-kits (Phase 2, TODO: register)
  services/
    rankings.py      # compute_weighted_rankings(), flatten_db_rankings()
    cache.py         # CacheService — Upstash-compatible Redis, 6h TTL
    exports.py       # generate_excel(), generate_pdf()
  tests/
    conftest.py      # `client` fixture (TestClient wrapping app)
    test_health.py
    repositories/    # test_players.py (more needed: sources, rankings)
    services/        # TODO: test_rankings.py, test_cache.py, test_exports.py
    routers/         # TODO: test_rankings.py, test_sources.py, test_exports.py, test_stripe.py, test_user_kits.py
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
| `models/schemas.py` | ✅ Complete | All Phase 2 schemas defined |
| `repositories/` | ✅ Complete | players, rankings, sources |
| `services/rankings.py` | ✅ Complete | `compute_weighted_rankings`, `flatten_db_rankings` |
| `services/cache.py` | ✅ Complete | `CacheService` with Upstash Redis |
| `services/exports.py` | ✅ Complete | `generate_excel`, `generate_pdf` |
| `routers/sources.py` | ✅ Complete | GET /sources |
| `core/dependencies.py` | ⬜ TODO | FastAPI Depends() injection functions |
| `routers/rankings.py` | ⬜ TODO | POST /rankings/compute |
| `routers/exports.py` | ⬜ TODO | POST /exports/generate |
| `routers/stripe.py` | ⬜ TODO | POST /stripe/create-checkout-session + webhook |
| `routers/user_kits.py` | ⬜ TODO | GET/POST/DELETE /user-kits |
| `main.py` router includes | ⬜ TODO | include all 4 new routers |
| `core/config.py` new fields | ⬜ TODO | redis_url, stripe_secret_key, stripe_webhook_secret, frontend_url |
| `pyproject.toml` new deps | ⬜ TODO | redis, stripe, openpyxl, weasyprint |
| Backend tests | ⬜ TODO | services/, routers/ test suites |

---

## Rankings Algorithm

```
POST /rankings/compute:
  1. Validate weights (all values >= 0)
  2. CacheService.get_rankings(season, weights)  →  cache hit: return with cached=True
  3. Cache miss:
       rows = RankingsRepository.get_by_season(season)
       source_rankings = flatten_db_rankings(rows)
       ranked = compute_weighted_rankings(source_rankings, weights)
       CacheService.set_rankings(season, weights, ranked)
  4. Return RankingsComputeResponse(cached=False, rankings=ranked)
```

Normalisation: rank 1 → score 1.0, rank N → score ≈ 0.0.
Missing-source grace: only sources with data for a player contribute to its
total weight — no redistribution needed by the caller.

---

## Key Schemas (`models/schemas.py`)

| Schema | Used by |
|--------|---------|
| `SourceOut` | GET /sources |
| `RankingsComputeRequest` / `RankingsComputeResponse` | POST /rankings/compute |
| `RankedPlayer` | nested in RankingsComputeResponse.rankings |
| `ExportRequest` / `ExportJobResponse` | POST /exports/generate |
| `CheckoutSessionRequest` / `CheckoutSessionResponse` | POST /stripe/create-checkout-session |
| `UserKitCreate` / `UserKitOut` | POST/GET /user-kits |

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
