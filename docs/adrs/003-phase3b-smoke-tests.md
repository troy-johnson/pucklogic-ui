# Phase 3b — Scraper Smoke Tests: Implementation Spec

**Date:** 2026-03-20
**Status:** Approved
**Branch:** `feat/3b-smoke-test`
**Milestone:** Phase 3b (see Phase 3 overall design: `2026-03-18-phase3-ml-trends-design.md`)

---

## Goal

Verify each Phase 3a scraper writes correct, non-null data to a real Postgres instance before building the feature engineering pipeline (3c). Tests run against the local Supabase CLI stack — not production.

---

## Approach

- New `apps/api/tests/smoke/` directory, excluded from the standard CI `pytest` run
- Real HTTP calls — no mocks (detects field-name mismatches and real API shape changes)
- Session-scoped fixtures: `db` (supabase client), `pg` (raw psycopg2 for SQL assertions)
- NHL.com runs first via `nhl_com_done` session fixture — populates `players` table via `nhl_id` upsert, which all name-matcher scrapers depend on
- `scripts/run_smoke_tests.sh` script handles env setup and stack health check

---

## Files to Create

```
apps/api/tests/smoke/
    __init__.py
    conftest.py                    # session fixtures
    test_smoke_nhl_com.py
    test_smoke_moneypuck.py
    test_smoke_nst.py
    test_smoke_hockey_reference.py
    test_smoke_elite_prospects.py
    test_smoke_nhl_edge.py
scripts/
    run_smoke_tests.sh
```

## Files to Modify

`apps/api/pyproject.toml`:
- Add `--ignore=tests/smoke` to `addopts`
- `tests/*` in `[tool.coverage.run] omit` already covers smoke; verify it's present
- Add `[project.optional-dependencies] smoke` group with `psycopg2-binary>=2.9.0`
  - Keep separate from `dev` — psycopg2-binary has platform-specific build issues on Alpine Linux and must not be installed in standard CI

---

## Fixture Design (`tests/smoke/conftest.py`)

```python
SMOKE_SEASON = "2025-26"

# Supabase CLI local defaults
SUPABASE_LOCAL_URL = "http://localhost:54321"
SUPABASE_LOCAL_SERVICE_ROLE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0"
    ".EGIM96RAZx35lJzdJsyH-qQwv8Hj04zWl196z2-SBc0"
)
SUPABASE_LOCAL_DB_URL = "postgresql://postgres:postgres@localhost:54322/postgres"

@pytest.fixture(scope="session")
def smoke_season() -> str: ...

@pytest.fixture(scope="session")
def db() -> supabase.Client:
    # env: SMOKE_SUPABASE_URL, SMOKE_SUPABASE_SERVICE_ROLE_KEY

@pytest.fixture(scope="session")
def pg():
    # psycopg2.connect — raw SQL, bypasses PostgREST/RLS
    # env: SMOKE_DATABASE_URL

@pytest.fixture(scope="session")
async def nhl_com_done(db, smoke_season):
    # MUST be async — do NOT use asyncio.run() here.
    # asyncio_mode="auto" with pytest-asyncio>=0.24 manages the session loop.
    # asyncio.run() inside the managed loop raises RuntimeError: loop already running.
    count = await NhlComScraper().scrape(smoke_season, db)
    assert count >= 500
    return count

@pytest.fixture(scope="session", autouse=True)
def cleanup_smoke_data(pg, smoke_season):
    yield
    # Best-effort — only runs if session completes normally.
    # Reliable cleanup: supabase db reset
    DELETE FROM player_stats WHERE season = smoke_season
    DELETE FROM player_rankings WHERE season = smoke_season
```

---

## Per-Scraper Tests

Each module: `test_scrape_completes`, `test_key_columns_non_null`, `test_column_range_sanity`, `test_match_rate`.

### Pass Criteria

| Scraper | Min rows | Match threshold | Key columns |
|---|---|---|---|
| NHL.com | 500 | n/a | `gp`, `g`, `a` |
| MoneyPuck | 500 | 95% | `ixg_per60`, `g_minus_ixg`, `xgf_pct_5v5` |
| NST | 500 | 95% (main) / 80% (situation cols) | `cf_pct`, `toi_ev`, `toi_pp`, `toi_sh`, `p1_per60`, `pdo`, `scf_per60` |
| Hockey Reference | 500 | 95% | `sh_pct_career_avg` (0.0–1.0), `nhl_experience` (≥1) |
| Elite Prospects | 200 | 80% | `elc_flag`, `contract_year_flag` (no nulls — schema default=false) |
| NHL EDGE | 0 (warn only) | n/a | `speed_bursts_22` (≥0), `top_speed` (15–35 mph) |

### Special Cases

**Elite Prospects**
```python
@pytest.mark.skipif(not os.environ.get("SMOKE_ELITE_PROSPECTS_API_KEY"), reason="no API key")
class TestEliteProspectsSmoke: ...
```

**NHL EDGE — soft-fail pattern**

Field names in `nhl_edge.py` are explicitly documented as approximate. Zero rows = field name mismatch. Test pattern:
```python
if count == 0:
    warnings.warn(
        f"NHL EDGE: 0 rows for {season} — verify sprintBurstsPerGame + topSpeed in _parse_response",
        UserWarning,
    )
# Wrap the count==0 branch in pytest.warns(UserWarning) context manager
# WARNING: pytest.warns() asserts a warning WAS raised — requires explicit warnings.warn() call above
```

If zero rows: inspect raw API JSON → update `_parse_response` in `nhl_edge.py` → update `nhl_edge_sample.json` fixture → rerun.

**NST — situation fetch failures**

`NstScraper.scrape()` makes 5 HTTP requests. `toi_ev`, `toi_pp`, `toi_sh` come from 3 separate situation-specific fetches. If a fetch fails silently, the overall row count is still nonzero (based on the `all` fetch). Use a separate `test_situation_columns_populated` assertion at 80% threshold (not 95%) with a comment pointing to the 4 situation URLs as the likely failure point.

**Hockey Reference — `sh_pct_career_avg` semantics**

`HockeyReferenceScraper.scrape()` calls `_fetch_prior_career()`. In a freshly reset DB there is no prior career data, so `sh_pct_career_avg` reflects the current season only (still within the 0.0–1.0 range check). Add a comment noting that `scrape_history()` over a 2-season window is required for true career-average verification.

**MoneyPuck — return value caveat**

`MoneyPuckScraper.scrape()` returns `len(players)` (ranking rows), not the count of `player_stats` rows written. `xgf_pct_5v5` is only written when a 5v5 row exists for the NHL ID. The SQL assertion is the ground truth — document this disconnect in a comment.

---

## Verification SQL (examples)

```sql
-- NST match rate
SELECT COUNT(cf_pct)::float / NULLIF(COUNT(*), 0) FROM player_stats WHERE season='2025-26';
-- >= 0.95

-- NST situation columns (lower threshold — separate HTTP fetches)
SELECT COUNT(toi_ev)::float / NULLIF(COUNT(*), 0) FROM player_stats WHERE season='2025-26';
-- >= 0.80

-- Hockey Reference range guard (fraction, not percentage)
SELECT COUNT(*) FROM player_stats
WHERE season='2025-26' AND sh_pct_career_avg IS NOT NULL
  AND (sh_pct_career_avg < 0 OR sh_pct_career_avg > 1.0);
-- 0 rows expected

-- NHL EDGE plausibility
SELECT COUNT(*) FROM player_stats
WHERE season='2025-26' AND top_speed IS NOT NULL AND (top_speed < 15 OR top_speed > 35);
-- 0 rows expected
```

---

## `scripts/run_smoke_tests.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../apps/api"

if ! curl -s http://localhost:54321/rest/v1/ > /dev/null 2>&1; then
    echo "ERROR: Run 'supabase start' first"; exit 1
fi

SUPABASE_LOCAL_SERVICE_ROLE="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hj04zWl196z2-SBc0"

export SMOKE_SUPABASE_URL="${SMOKE_SUPABASE_URL:-http://localhost:54321}"
export SMOKE_SUPABASE_SERVICE_ROLE_KEY="${SMOKE_SUPABASE_SERVICE_ROLE_KEY:-$SUPABASE_LOCAL_SERVICE_ROLE}"
export SMOKE_DATABASE_URL="${SMOKE_DATABASE_URL:-postgresql://postgres:postgres@localhost:54322/postgres}"

pytest tests/smoke/ -v -p no:cov --tb=short
```

---

## Prerequisites

```bash
brew install supabase/tap/supabase   # if not already installed
```

## How to Run

```bash
# First time only (generates supabase/config.toml):
supabase init

supabase start
supabase db reset                    # applies migrations 001–004 in order
pip install -e ".[dev,smoke]"        # adds psycopg2-binary
./scripts/run_smoke_tests.sh
```

Standard suite is unaffected: `pytest` excludes `tests/smoke/` via `--ignore` in `addopts`.
