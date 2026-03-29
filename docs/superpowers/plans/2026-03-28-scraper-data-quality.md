# Plan: Scraper Data Quality — Traded Player Dedup, NHL.com Aggregation, NST toi_sh Bug, V2 Per-Team Schema

**Spec basis:** DB audit 2026-03-28 against Supabase project `mrjrtwwmbxfytnnjkaid`
**Branch:** `feat/scraper-data-quality`
**Risk Tier:** 2 — Cross-module
**Scope:** Medium (~4–6h, 1–2 sessions)
**Reviewer policy:** 1 external minimum (Gemini or Codex)

---

## Execution Status Update (2026-03-29)

### Completed

- Migration `005_hits_blocks_per60.sql` applied to production (`mrjrtwwmbxfytnnjkaid`)
- `scripts/backfill_data_quality.sh` implemented and used for staged sample/full validation
- NST historical matcher coverage fixed via paginated players/aliases fetch
- NST and NHL.com historical runners now support bounded season windows (`--start-season`, `--end-season`)
- Validation rule corrected from `toi_sh < toi_ev` to source-correct non-negative TOI checks
- Non-destructive `player_stats` upserts enforced (`default_to_null=False`) to prevent partial payload null-overwrites
- Targeted reruns performed to resolve validation anomalies (`NST 2009-10`, `NHL 2009-10`, `NHL 2024-25`)
- Hockey Reference targeted verification backfill rerun completed (`2009-10..2010-11`, 336 rows)
- First real ML run completed for `2026-27` (artifacts uploaded, `player_trends` written)
- Trends API hardened for legacy positions (`L/R`) and Supabase pagination limits
- Final validation baseline:
  - raw `hits`/`blocks` coverage strong from `2005-06` onward
  - per-60 `hits_per60`/`blocks_per60` coverage strong from `2007-08` onward
  - no negative `toi_ev` / `toi_pp` / `toi_sh` values

### Remaining execution items

- Await PR review/merge for branch `feat/scraper-data-quality` (PR #30).
- Address any review feedback, then proceed to draft-kit UI workflow lock.

---

## Goals

1. Fix `hits`/`blocks` NULL for alternating seasons (NHL.com history silently skips seasons on error)
2. Fix `hits`/`blocks` NULL for ~4% of players per populated season (realtime pass misses players not in `nhl_id_map`)
3. Fix `toi_sh` storing `toi_per_game` instead of SH TOI/game (NST `sit=sh` parse bug)
4. Fix Hockey Reference career stat overcounting for multi-trade seasons (2TM/3TM/4TM dedup) **(implemented; verification rerun pending)**
5. Populate `hits_per60`/`blocks_per60` — migration 005 confirmed applied; NST history rerun + validation completed
6. Deprecate `pp_toi_pg` (zero rows ever written; superseded by `toi_pp` from NST)
7. Add `player_team_stats` V2 schema (schema-only; no scraper writer in this PR)
8. Add `scripts/backfill_data_quality.sh` — post-merge re-run helper with verification SQL (implemented)

## Non-Goals

- Per-team tracking **implementation** (V2/Phase 4 — schema only in this PR)
- NST historical coverage gaps pre-2014 (data availability limit, not a bug)
- `cf_pct_rel`, `gar`, `xgar`, `ozs_pct`, `speed_bursts_22`, `top_speed` (no current source)

---

## Confirmed DB State (audit baseline 2026-03-28)

| Column | Status |
|---|---|
| `hits` / `blocks` | 0% in 2024-25, 2022-23, 2016-17 (partial), 2013-14 (partial), 2010-11 (partial) |
| `hits` / `blocks` within populated seasons | ~4% null (realtime pass misses) |
| `hits_per60` / `blocks_per60` | 0 rows across all 18,888 rows |
| `pp_toi_pg` | 0 rows across all 18,888 rows |
| `toi_sh` | Stores `toi_per_game` exactly — confirmed via McDavid (23.03), Lars Eller (11.45) |
| `toi_pp` | Correct — per game minutes (McDavid: 3.61) |
| Migration 005 | Applied ✅ — `hits_per60`, `blocks_per60` columns exist |

---

## Files to Create / Modify

| File | Change |
|---|---|
| `scrapers/nhl_com.py` | `isAggregate=false→true`; handle comma `teamAbbrevs`; realtime fallback by `nhl_id`; per-season logging |
| `scrapers/nst.py` | Fix `toi_sh` parsing bug (sit=sh TOI column header mismatch) |
| `scrapers/hockey_reference.py` | Dedup multi-team rows — keep highest-GP row per player per season |
| `tests/scrapers/test_nhl_com.py` | Tests for aggregate URL, comma teamAbbrevs, realtime fallback |
| `tests/scrapers/test_nst.py` | Tests for `toi_sh` correctness with sit=sh fixture |
| `tests/scrapers/test_hockey_reference.py` | Tests for 2TM/3TM/4TM dedup, career stat correctness |
| `supabase/migrations/006_deprecate_pp_toi_pg_add_player_team_stats.sql` | Deprecate `pp_toi_pg`; add `player_team_stats` V2 table |
| `docs/backend-reference.md` | Update scraper runbook; document deprecation and V2 schema |
| `scripts/backfill_data_quality.sh` | Post-merge re-run helper with verification SQL |
| `.claude/SESSION_STATE.md` | Update on merge |

---

## Implementation Phases (TDD)

### Phase 1 — NHL.com scraper

**1a. `isAggregate=true` on both URL builders**
With `isAggregate=false`, traded players produce one row per team; the second upsert overwrites the first,
losing one team's `hits`/`blocks`. With `true`, API returns one row per player per season (full combined totals).
`teamAbbrevs` becomes comma-joined for traded players — store last team.

**1b. Realtime pass fallback**
Players not in `nhl_id_map` (defensive specialists, low-point traded players) are silently skipped.
Add `_lookup_player_by_nhl_id(db, nhl_id)` fallback before skipping.

**1c. Per-season realtime row count logging**
History output shows `780 summary rows, 756 realtime rows` per season — silent 0-realtime seasons become visible.

### Phase 2 — NST `toi_sh` fix

`toi_sh` stores `toi_per_game` exactly for every player. Root cause: the NST `sit=sh` page likely uses
`"TOI/GP"` as the column header instead of `"TOI"`, causing `_parse_html` to fail finding the column and
`_merge_situation_rows` inheriting the stale all-situations value. Fix: add `"TOI/GP"` as fallback header.

### Phase 3 — Hockey Reference dedup

Multi-team seasons produce 3+ rows (e.g. `3TM`, `CAR`, `EDM`, `CGY`). `_compute_career_stats` accumulates
all rows, tripling goals/shots. Fix: after parsing, keep only the highest-GP row per player name.
The aggregate row always has the highest GP. Works for 2TM/3TM/4TM uniformly.

### Phase 4 — Migration + helper script

Migration 006: comment-deprecate `pp_toi_pg`; add `player_team_stats` V2 schema (schema-only).
Helper script: `scripts/backfill_data_quality.sh`.

---

## V2 Per-Team Tracking Scope

`player_team_stats` enables Phase 4 Layer 2 in-season signals:
- Pre-trade vs post-trade production rates
- Team context: PP%, team SH%, team xGF/60
- PP unit assignment per team segment
- In-season projection adjustment (last 20 GP on new team vs full-season blend)

ML training pipeline (Phase 3) continues to use `player_stats` season aggregates unchanged.

V2 implementation (not this PR): NHL.com team-split pass → `player_team_stats`; Layer 2 inference endpoint.

---

## TDD Sequence

```
Phase 1 — NHL.com:
  RED  test_build_url_uses_aggregate_true
  FIX  _build_url
  RED  test_build_realtime_url_uses_aggregate_true
  FIX  _build_realtime_url
  RED  test_traded_player_team_stored_as_last_team
  FIX  _upsert_player teamAbbrevs
  RED  test_realtime_fallback_looks_up_by_nhl_id
  FIX  add _lookup_player_by_nhl_id + realtime fallback
  GREEN test_realtime_skips_when_not_in_map_or_db

Phase 2 — NST toi_sh:
  RED  test_parse_sh_toi_returns_sh_toi_not_all_situations_toi
  FIX  _parse_html TOI column header fallback
  GREEN test_toi_sh_does_not_equal_toi_per_game
  GREEN test_toi_sh_is_none_for_player_with_no_pk_time

Phase 3 — Hockey Reference:
  RED  test_traded_player_two_teams_keeps_aggregate
  FIX  _parse_html dedup by highest gp
  RED  test_traded_player_four_teams_keeps_highest_gp
  GREEN test_non_traded_player_unaffected
  RED  test_career_stats_correct_after_dedup
  GREEN test_equal_gp_keeps_first_row (document assumption)

Phase 4:
  Write migration 006
  Write scripts/backfill_data_quality.sh
  Full suite green + ruff clean
```

---

## Post-Merge Checklist

```
[x] Run scripts/backfill_data_quality.sh
[x] Verify hits/blocks ≥95% for all post-2006 seasons
[x] Verify hits_per60 / blocks_per60 > 0 for 2008-09 onward
[x] Verify non-negative `toi_ev`, `toi_pp`, `toi_sh` values for all players (0 violations)
[ ] Verify career_goals not inflated for known traded players after HR verification rerun
[x] Run ml.train --season 2026-27
[ ] Update SESSION_STATE.md / active state after PR #30 review+merge to transition into draft-kit workflow lock
```
