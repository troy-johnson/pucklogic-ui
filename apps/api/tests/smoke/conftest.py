"""
Shared fixtures for Phase 3b scraper smoke tests.

Prerequisites
-------------
1. Supabase CLI stack running:  supabase start
2. All migrations applied:      supabase db reset
3. Python deps installed:       pip install -e ".[dev,smoke]"

Then run:  ./scripts/run_smoke_tests.sh

Environment variables (all have working defaults for the local Supabase CLI stack):
  SMOKE_SUPABASE_URL             default: http://localhost:54321
  SMOKE_SUPABASE_SERVICE_ROLE_KEY  default: well-known Supabase CLI service-role JWT
  SMOKE_DATABASE_URL             default: postgresql://postgres:postgres@localhost:54322/postgres

Notes
-----
- ``nhl_com_done`` is an async session fixture.  Do NOT use asyncio.run() here;
  pytest-asyncio>=0.24 with asyncio_mode="auto" manages the session event loop.
  Calling asyncio.run() inside the managed loop raises RuntimeError.
- ``cleanup_smoke_data`` is best-effort: it runs only if the session completes
  normally.  For guaranteed cleanup between runs, use:  supabase db reset
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import psycopg2
import pytest
from supabase import Client, create_client

from scrapers.nhl_com import NhlComScraper

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SMOKE_SEASON = "2025-26"

# Supabase CLI defaults — safe to hard-code, these are well-known local-only values.
_DEFAULT_SUPABASE_URL = "http://localhost:54321"
_DEFAULT_SERVICE_ROLE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0"
    ".EGIM96RAZx35lJzdJsyH-qQwv8Hj04zWl196z2-SBc0"
)
_DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:54322/postgres"


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def smoke_season() -> str:
    return SMOKE_SEASON


@pytest.fixture(scope="session")
def db() -> Client:
    """Real Supabase client pointed at the local CLI stack."""
    url = os.environ.get("SMOKE_SUPABASE_URL", _DEFAULT_SUPABASE_URL)
    key = os.environ.get("SMOKE_SUPABASE_SERVICE_ROLE_KEY", _DEFAULT_SERVICE_ROLE_KEY)
    return create_client(url, key)


@pytest.fixture(scope="session")
def pg() -> Generator[Any, None, None]:
    """Raw psycopg2 connection for SQL assertion queries.

    Bypasses PostgREST / RLS entirely — this is the ground truth.
    """
    database_url = os.environ.get("SMOKE_DATABASE_URL", _DEFAULT_DATABASE_URL)
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session")
async def nhl_com_done(db: Client, smoke_season: str) -> int:
    """Run NhlComScraper once to populate ``players`` and ``player_stats``.

    All name-matcher scrapers (NST, Hockey Reference, Elite Prospects, NHL EDGE)
    depend on ``players`` being populated.  This fixture MUST complete before any
    of those tests run.

    Returns the upserted row count.
    """
    count = await NhlComScraper().scrape(smoke_season, db)
    assert count >= 500, (
        f"NHL.com prerequisite failed: only {count} rows written. "
        "Check network access to api.nhle.com."
    )
    return count


@pytest.fixture(scope="session", autouse=True)
def cleanup_smoke_data(pg: Any, smoke_season: str) -> Generator[None, None, None]:
    """Delete smoke-test rows from player_stats and player_rankings at session end.

    Best-effort: only executes when the session completes normally.
    For reliable cleanup between smoke runs, use:  supabase db reset
    """
    yield
    with pg.cursor() as cur:
        cur.execute("DELETE FROM player_stats WHERE season = %s", (smoke_season,))
        cur.execute("DELETE FROM player_rankings WHERE season = %s", (smoke_season,))
        # The @pytest.mark.slow scrape_history test writes season "2024-25" rows
        # (always one season behind smoke_season). Clean those up too so a slow-test
        # run does not leave residual data in the local DB.
        cur.execute("DELETE FROM player_stats WHERE season = '2024-25'")


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------


def query_count(pg: Any, sql: str, *params: Any) -> int:
    """Execute a COUNT(*) query and return the integer result."""
    with pg.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return int(row[0]) if row else 0


def query_value(pg: Any, sql: str, *params: Any) -> Any:
    """Execute a scalar-value query and return the first column of the first row."""
    with pg.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
