#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "python3 not found on PATH; set PYTHON_BIN explicitly" >&2
  exit 1
fi

PROJECT_ID="${SUPABASE_PROJECT_ID:-mrjrtwwmbxfytnnjkaid}"
HISTORY_START="${HISTORY_START:-2005-06}"
NST_HISTORY_START="${NST_HISTORY_START:-$HISTORY_START}"
NHL_HISTORY_START="${NHL_HISTORY_START:-$HISTORY_START}"
SAMPLE_START="${SAMPLE_START:-2005-06}"
SAMPLE_END="${SAMPLE_END:-2005-06}"
MIN_SAMPLE_ROWS="${MIN_SAMPLE_ROWS:-50}"
MIN_SEASON_ROWS="${MIN_SEASON_ROWS:-50}"
MIN_COVERAGE_PCT="${MIN_COVERAGE_PCT:-95}"
RATE_REQUIRED_START="${RATE_REQUIRED_START:-$NST_HISTORY_START}"
RAW_REQUIRED_START="${RAW_REQUIRED_START:-$NHL_HISTORY_START}"

CURRENT_SEASON="$(
  cd "$API_DIR"
    "$PYTHON_BIN" - <<'PY'
from core.config import settings
print(settings.current_season)
PY
)"
CURRENT_SEASON="${CURRENT_SEASON//$'\r'/}"

HISTORY_END="${HISTORY_END:-$CURRENT_SEASON}"

run_scraper_history() {
  local scraper_module="$1"
  local start_season="$2"
  local end_season="$3"

  echo "==> Running ${scraper_module} history for ${start_season}..${end_season}"
  (
    cd "$API_DIR"
    "$PYTHON_BIN" -m "$scraper_module" --history --start-season "$start_season" --end-season "$end_season"
  )
}

run_validation() {
  local mode="$1"
  local start_season="$2"
  local end_season="$3"

  echo "==> Validating ${mode} range ${start_season}..${end_season}"
  (
    cd "$API_DIR"
    VALIDATION_MODE="$mode" \
    VALIDATION_START="$start_season" \
    VALIDATION_END="$end_season" \
    VALIDATION_MIN_SAMPLE_ROWS="$MIN_SAMPLE_ROWS" \
    VALIDATION_MIN_SEASON_ROWS="$MIN_SEASON_ROWS" \
    VALIDATION_MIN_COVERAGE_PCT="$MIN_COVERAGE_PCT" \
    VALIDATION_RATE_REQUIRED_START="$RATE_REQUIRED_START" \
    VALIDATION_RAW_REQUIRED_START="$RAW_REQUIRED_START" \
    "$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import os
from collections import defaultdict

from supabase import create_client

from core.config import settings


def fetch_player_stats(db, start_season: str, end_season: str) -> list[dict]:
    rows: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        response = (
            db.table("player_stats")
            .select(
                "season,gp,hits,blocks,hits_per60,blocks_per60,toi_ev,toi_pp,toi_sh",
                count="exact",
            )
            .gte("season", start_season)
            .lte("season", end_season)
            .order("season")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator / denominator) * 100.0


mode = os.environ["VALIDATION_MODE"]
start_season = os.environ["VALIDATION_START"]
end_season = os.environ["VALIDATION_END"]
min_sample_rows = int(os.environ["VALIDATION_MIN_SAMPLE_ROWS"])
min_season_rows = int(os.environ["VALIDATION_MIN_SEASON_ROWS"])
min_coverage_pct = float(os.environ["VALIDATION_MIN_COVERAGE_PCT"])
rate_required_start = os.environ["VALIDATION_RATE_REQUIRED_START"]
raw_required_start = os.environ["VALIDATION_RAW_REQUIRED_START"]

db = create_client(settings.supabase_url, settings.supabase_service_role_key)
rows = fetch_player_stats(db, start_season, end_season)
if not rows:
    raise SystemExit(f"validation failed: no player_stats rows found for {start_season}..{end_season}")

season_totals: dict[str, int] = defaultdict(int)
season_gp_rows: dict[str, int] = defaultdict(int)
season_rate_rows: dict[str, int] = defaultdict(int)
season_raw_rows: dict[str, int] = defaultdict(int)
negative_toi_values: list[tuple[str, str, float]] = []

for row in rows:
    season = row["season"]
    season_totals[season] += 1
    gp = row.get("gp")
    if gp is not None:
        season_gp_rows[season] += 1
    if row.get("hits_per60") is not None and row.get("blocks_per60") is not None:
        season_rate_rows[season] += 1
    if row.get("hits") is not None and row.get("blocks") is not None:
        season_raw_rows[season] += 1
    for toi_field in ("toi_ev", "toi_pp", "toi_sh"):
        toi_value = row.get(toi_field)
        if toi_value is not None and toi_value < 0:
            negative_toi_values.append((season, toi_field, toi_value))

print(f"Validation mode: {mode}")
print(f"Seasons checked: {start_season}..{end_season}")

coverage_failures: list[str] = []
raw_failures: list[str] = []
for season in sorted(season_totals):
    total = season_totals[season]
    gp_rows = season_gp_rows[season]
    rate_rows = season_rate_rows[season]
    raw_rows = season_raw_rows[season]
    denominator = gp_rows or total
    coverage_pct = pct(rate_rows, denominator)
    raw_pct = pct(raw_rows, denominator)
    print(
        f"  {season}: total={total} gp_rows={gp_rows} rate_rows={rate_rows} "
        f"raw_rows={raw_rows} rate_coverage={coverage_pct:.1f}% raw_coverage={raw_pct:.1f}%"
    )
    if season >= rate_required_start:
        if rate_rows < min_season_rows or coverage_pct < min_coverage_pct:
            coverage_failures.append(
                f"{season} rate_rows={rate_rows} coverage={coverage_pct:.1f}%"
            )
    if season >= raw_required_start:
        if raw_rows < min_season_rows or raw_pct < min_coverage_pct:
            raw_failures.append(f"{season} raw_rows={raw_rows} coverage={raw_pct:.1f}%")

sample_rate_rows = sum(season_rate_rows.values())
sample_raw_rows = sum(season_raw_rows.values())

if mode == "sample":
    if sample_rate_rows < min_sample_rows:
        raise SystemExit(
            f"validation failed: sample rate rows {sample_rate_rows} < minimum {min_sample_rows}"
        )
    if sample_raw_rows < min_sample_rows:
        raise SystemExit(
            f"validation failed: sample raw rows {sample_raw_rows} < minimum {min_sample_rows}"
        )

if coverage_failures:
    raise SystemExit("validation failed: rate coverage failures: " + "; ".join(coverage_failures))
if raw_failures:
    raise SystemExit("validation failed: raw coverage failures: " + "; ".join(raw_failures))
if negative_toi_values:
    details = ", ".join(
        f"{season}({toi_field}={toi_value})"
        for season, toi_field, toi_value in negative_toi_values[:10]
    )
    raise SystemExit(f"validation failed: negative TOI values found: {details}")

print("Validation passed.")
PY
  )
}

echo "==> Backfill data quality run starting"
echo "    project:           $PROJECT_ID"
echo "    sample:            $SAMPLE_START..$SAMPLE_END"
echo "    nst full:          $NST_HISTORY_START..$HISTORY_END"
echo "    nhl full:          $NHL_HISTORY_START..$HISTORY_END"
echo "    rate required:     $RATE_REQUIRED_START..$HISTORY_END"
echo "    raw required:      $RAW_REQUIRED_START..$HISTORY_END"

(
  cd "$API_DIR"
    "$PYTHON_BIN" - <<'PY'
from core.config import settings

missing = []
if not settings.supabase_url:
    missing.append("supabase_url")
if not settings.supabase_service_role_key:
    missing.append("supabase_service_role_key")
if missing:
    raise SystemExit(f"missing required settings: {', '.join(missing)}")
print(f"Supabase URL configured for {settings.supabase_url}")
PY
)

run_scraper_history scrapers.nst "$SAMPLE_START" "$SAMPLE_END"
run_scraper_history scrapers.nhl_com "$SAMPLE_START" "$SAMPLE_END"
run_validation sample "$SAMPLE_START" "$SAMPLE_END"

run_scraper_history scrapers.nst "$NST_HISTORY_START" "$HISTORY_END"
run_scraper_history scrapers.nhl_com "$NHL_HISTORY_START" "$HISTORY_END"
run_validation full "$RAW_REQUIRED_START" "$HISTORY_END"

echo "==> Backfill data quality run completed successfully"
