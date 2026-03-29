# Backfill Data Quality Runner — Implementation Spec

- **Date:** 2026-03-28
- **Status:** Approved
- **Related plan:** `docs/superpowers/plans/2026-03-28-scraper-data-quality.md`
- **Effort:** Small
- **Risk:** Tier 3 — production schema migration + historical backfill
- **Reviewer policy:** sample-first execution, fail-fast validation, explicit production safeguards

## Implementation Notes

- This spec captures the approved follow-up work after scraper hardening on `feat/scraper-data-quality`.
- Supabase currently has a single production project, so the backfill workflow must be safe for direct production execution.
- Migration `005_hits_blocks_per60.sql` is part of this scope and must land before the NST/NHL.com history reruns.

## Architecture References

- `docs/pucklogic-architecture.md`
- `docs/backend-reference.md`
- `docs/superpowers/plans/2026-03-28-scraper-data-quality.md`
- `apps/api/CLAUDE.md`

## Goals

1. Apply migration 005 so `player_stats` has `hits_per60` and `blocks_per60`.
2. Add a repo-native helper script at `scripts/backfill_data_quality.sh`.
3. Make the helper run a safe staged workflow:
   - preflight checks
   - sample history rerun
   - database validation
   - full history rerun only if sample validation passes
   - final database validation across the full historical window
4. Support bounded history reruns for NST and NHL.com so the helper can run a sample range before the full range.

## Non-Goals

1. Finish Hockey Reference traded-player/career dedup.
2. Run the first ML training cycle.
3. Introduce migration 006 or any new schema beyond migration 005.
4. Build a generalized data-ops framework beyond this specific backfill workflow.

## Design Decisions

| ID | Decision | Why |
| --- | --- | --- |
| D1 | Use existing scraper CLIs instead of a new backfill subsystem. | Keeps the implementation surface small and reuses known-good code paths. |
| D2 | Add bounded history support via `--start-season` / `--end-season`. | Enables a safe sample-first run without invasive scraper refactors. |
| D3 | Use a season-bounded sample rather than exact row-cutoff interruption. | Safer than aborting midway through a season while still validating real writes quickly. |
| D4 | Validate by querying `player_stats` after the sample and after the full run. | Confirms the database actually contains the expected values, not just that the scrapers exited successfully. |
| D5 | Treat `hits_per60` / `blocks_per60` as required from `2005-06` onward. | Matches the current product requirement and approved launch-readiness direction. |

## Workflow

1. Apply migration `005_hits_blocks_per60.sql` to production.
2. Run sample rerun for `2005-06` first:
   - `python -m scrapers.nst --history --start-season 2005-06 --end-season 2005-06`
   - `python -m scrapers.nhl_com --history --start-season 2005-06 --end-season 2005-06`
3. Query `player_stats` and require:
   - at least ~50 sample rows with both `hits_per60` and `blocks_per60`
   - at least ~50 sample rows with raw `hits` and `blocks`
   - no negative situation TOI values for `toi_ev`, `toi_pp`, or `toi_sh`
4. If the sample passes, rerun full history from `2005-06` through `current_season` for NST and NHL.com.
5. Re-run validation across the full range and fail if any season falls below the expected thresholds, allowing separate required start seasons for raw NHL data vs NST per-60 rate data when source coverage differs.

## Module / File Layout

- `apps/api/scrapers/nst.py`
  - add bounded history CLI arguments
- `apps/api/scrapers/nhl_com.py`
  - add bounded history CLI arguments
- `apps/api/tests/scrapers/test_nst.py`
  - add tests for bounded season iteration behavior
- `apps/api/tests/scrapers/test_nhl_com.py`
  - add tests for bounded season iteration behavior
- `scripts/backfill_data_quality.sh`
  - orchestrate preflight, sample, validation, full run, and final validation

## Validation Rules

Validation runs against `player_stats` and checks, by season:

1. sufficient rows with non-null `hits_per60` and `blocks_per60`
2. sufficient rows with non-null raw `hits` and `blocks`
3. at least 95% coverage among rows with `gp` when available
4. zero negative values in `toi_ev`, `toi_pp`, or `toi_sh`

Sample mode additionally requires at least 50 matching rows before the script proceeds to the full rerun.

## Acceptance Criteria

### Migration

- [ ] migration 005 is applied successfully to the production project

### Scraper entrypoints

- [ ] NST history CLI accepts bounded start/end seasons
- [ ] NHL.com history CLI accepts bounded start/end seasons
- [ ] invalid season ranges fail clearly

### Script

- [ ] `scripts/backfill_data_quality.sh` exists and is executable
- [ ] the script performs preflight checks before writing data
- [ ] the script runs a sample rerun and validates before starting the full rerun
- [ ] the script exits nonzero on validation failure

### Data validation

- [ ] sample validation confirms meaningful writes before full history proceeds
- [ ] final validation confirms `hits_per60` and `blocks_per60` are populated from the earliest supported NST season onward
- [ ] final validation confirms raw `hits` and `blocks` are populated from `2005-06` onward
- [ ] final validation confirms no negative situation TOI values

## Open Questions (resolved)

1. **Should the sample stage stop after an exact row count?** No. Use a season-bounded sample first, because it is safer and less invasive.
2. **Should this run against production directly?** Yes. There is only one Supabase environment right now.
3. **What historical range is required?** `2005-06` onward for both raw and per-60 physical stats.
