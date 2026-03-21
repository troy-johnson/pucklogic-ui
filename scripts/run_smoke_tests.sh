#!/usr/bin/env bash
# Phase 3b scraper smoke tests.
#
# Runs all scrapers end-to-end against the local Supabase CLI stack and
# asserts that expected columns are written with correct values.
#
# Prerequisites
# -------------
# 1. Install Supabase CLI (if not already):
#      brew install supabase/tap/supabase
# 2. First-time only — generate config.toml from repo root:
#      supabase init
# 3. Start the local stack and apply all migrations (001–004):
#      supabase start
#      supabase db reset    # applies supabase/migrations/*.sql in order
# 3. Install Python deps (from apps/api/):
#      pip install -e ".[dev,smoke]"
#
# Usage
# -----
#   ./scripts/run_smoke_tests.sh
#   SMOKE_ELITE_PROSPECTS_API_KEY=ep_xxx ./scripts/run_smoke_tests.sh
#
# Environment variables (all have defaults for the local Supabase CLI stack)
# --------------------------------------------------------------------------
#   SMOKE_SUPABASE_URL               default: http://localhost:54321
#   SMOKE_SUPABASE_SERVICE_ROLE_KEY  default: well-known Supabase CLI JWT
#   SMOKE_DATABASE_URL               default: postgresql://postgres:postgres@localhost:54322/postgres
#   SMOKE_ELITE_PROSPECTS_API_KEY    optional; Elite Prospects tests are skipped if unset

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"

# ---------------------------------------------------------------------------
# Resolve Python / pip via the project venv (apps/api/.venv)
# ---------------------------------------------------------------------------
VENV_DIR="$API_DIR/.venv"
if [ -f "$VENV_DIR/bin/pip" ]; then
    PIP="$VENV_DIR/bin/pip"
    PYTEST="$VENV_DIR/bin/pytest"
elif command -v pip3 &> /dev/null; then
    PIP="pip3"
    PYTEST="pytest"
elif command -v python3 &> /dev/null; then
    PIP="python3 -m pip"
    PYTEST="python3 -m pytest"
else
    echo "ERROR: No venv, pip3, or python3 found." >&2
    echo "Create a venv first:  cd apps/api && python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev,smoke]'" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Verify Supabase CLI stack is running
# ---------------------------------------------------------------------------
if ! curl -s http://localhost:54321/rest/v1/ > /dev/null 2>&1; then
    echo ""
    echo "ERROR: Supabase CLI stack is not running."
    echo ""
    echo "Start it with:"
    echo "  supabase start"
    echo "  supabase db reset    # applies all migrations"
    echo ""
    exit 1
fi

# ---------------------------------------------------------------------------
# Resolve Supabase local credentials from 'supabase status --output env'
# This avoids hard-coded JWTs that may not match the running instance's secret.
# ---------------------------------------------------------------------------
_STATUS_ENV=$(supabase status --output env 2>/dev/null || true)

_parse_status() {
    echo "$_STATUS_ENV" | grep "^$1=" | sed 's/^[^=]*=//; s/^"//; s/"$//'
}

_SUPABASE_LOCAL_URL=$(_parse_status "API_URL")
_SUPABASE_LOCAL_SERVICE_ROLE=$(_parse_status "SERVICE_ROLE_KEY")
_SUPABASE_LOCAL_DB_URL=$(_parse_status "DB_URL")

export SMOKE_SUPABASE_URL="${SMOKE_SUPABASE_URL:-${_SUPABASE_LOCAL_URL:-http://localhost:54321}}"
export SMOKE_SUPABASE_SERVICE_ROLE_KEY="${SMOKE_SUPABASE_SERVICE_ROLE_KEY:-$_SUPABASE_LOCAL_SERVICE_ROLE}"
export SMOKE_DATABASE_URL="${SMOKE_DATABASE_URL:-${_SUPABASE_LOCAL_DB_URL:-postgresql://postgres:postgres@localhost:54322/postgres}}"

if [ -z "$SMOKE_SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "ERROR: Could not determine SERVICE_ROLE_KEY from 'supabase status'." >&2
    echo "Set SMOKE_SUPABASE_SERVICE_ROLE_KEY manually or ensure supabase is running." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Ensure smoke deps (psycopg2-binary) are installed
# ---------------------------------------------------------------------------
cd "$API_DIR"
$PIP install -q -e ".[dev,smoke]"

# ---------------------------------------------------------------------------
# Run smoke tests
# ---------------------------------------------------------------------------
echo ""
echo "Running Phase 3b smoke tests against $SMOKE_SUPABASE_URL ..."
echo "Expected duration: 3–8 minutes (live HTTP, rate-limited scrapers)"
echo ""

$PYTEST tests/smoke/ -v --tb=short --override-ini="addopts=" "$@"

echo ""
echo "Smoke tests complete."
echo ""
echo "NOTE: Smoke data will be cleaned up automatically on session end."
echo "      For a guaranteed clean slate before the next run: supabase db reset"
