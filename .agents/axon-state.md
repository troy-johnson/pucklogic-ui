| Field | Value |
|---|---|
| Active Phase | Implement-TDD kickoff: execute 008b first, then 008c, with 010a limited to scaffold work until spec 010 is approved |
| Active Branch | feat/live-draft-sync-backend-contract |
| Open PR | #32 — https://github.com/troy-johnson/pucklogic-ui/pull/32 |
| Current Focus | Execute the active implementation set in dependency order: `docs/plans/008b-live-draft-backend.md` → `docs/plans/008c-extension-sync-adapters.md` → scaffold-only `docs/plans/010a-web-draft-kit-ui.md` under `docs/specs/009-web-draft-kit-ux.md` / draft `docs/specs/010-web-ui-wireframes-design.md` |
| Last Action | Closed the remaining `008b` verification loop: full focused draft-session backend suite now passes (`75 passed`) in `apps/api/.venv313`, PR evidence covers create → attach → pick ingestion → reconnect → manual fallback → resume/end plus reconnect-denial handling, and the future adapter metrics-export requirement was recorded in `008c` as a pre-launch item |
| Pending External | Legal/commercial review of third-party aggregated data usage before monetized extension launch |
| Current Hypothesis | WebSocket-backed backend authority is the critical first implementation slice; ESPN is MVP, Yahoo is secondary, manual mode remains the launch fallback, and launch infra is Fly.io single-instance with Redis deferred |
| Next Steps | 1. Begin `008c-extension-sync-adapters` with Wave 1 bootstrap + shared protocol TDD now that `008b` backend contract/verification is closed 2. Preserve the launch observability decision: backend logs + in-memory counters stay for now, while production metrics export remains a required pre-launch item in `008c` before go-live signoff 3. Keep `010a-web-draft-kit-ui` limited to scaffold work until spec 010 is approved |

## Merge and code review outcome (2026-04-10)

## Planning outcome (2026-04-10)

- Rewrote canonical spec `docs/specs/008-live-draft-sync-launch-required.md` as the non-UI live draft backend and sync contract.
- Archived the previous mixed-scope 008 draft at `docs/archive/2026-04-01-008-live-draft-sync-launch-required.md`.
- Updated `docs/specs/INDEX.md` to mark `008` approved with its narrowed canonical scope.
- Confirmed scope split: `008` owns backend/session/extension contract, `009` owns UX/product workflow, `010` owns wireframes/layout.
- Created branch `feat/live-draft-sync-backend-contract` and opened PR #32 for the spec/plan split.
- Updated PR #32 description with summary, test plan, and known limitations.

- Wrote implementation plan `docs/plans/008b-live-draft-backend.md` for backend session authority, entitlement checks, and WebSocket transport.
- Wrote implementation plan `docs/plans/010a-web-draft-kit-ui.md` for landing page, app shell, pre-draft workspace, live draft UI, and design tokens.
- Wrote implementation plan `docs/plans/008c-extension-sync-adapters.md` for extension bootstrap, ESPN MVP sync, Yahoo secondary sync, and manual fallback escalation.
- Updated `docs/plans/INDEX.md` to index the new plan set.
- Planning assumption now locked: final implementation uses WebSocket transport; Yahoo remains stretch acceptance and must not delay ESPN MVP readiness.
- Infra assumption now locked for launch planning: Fly.io single-instance backend, WebSocket primary, HTTP/manual fallback allowed, Redis deferred until scale requires it.
- Activated execution sequence on 2026-04-11: `008b` is the first implementation track, `008c` follows backend protocol stabilization, and `010a` is restricted to scaffold work until spec `010` leaves draft.

- Merged `main` (`c34f36b` scraper data quality hardening) into `feat/live-draft-sync-spec`.
- All conflicts resolved keeping HEAD: agent config paths (post-rename), `hockey_reference.py` stable dedup, `hockey_reference` test suite.
- Date-stamped plan/ADR files from main (`2026-03-28-*`) accepted at canonical `docs/plans/` and `docs/adrs/` paths; all are duplicates of existing numbered files and are not indexed separately.
- Addressed two Codex P2 findings in `nst.py`:
  - TOI fallback: blank/unparsable `toi_per_gp_col` now falls through to `total_TOI / GP` derivation instead of silently dropping stat.
  - Alias pagination: `_fetch_all_rows` now supports compound `order_by` (comma-separated); `_fetch_aliases` uses `alias_name,source` for stable offset-based paging.
- 52 nst tests passing; both Codex comment threads replied to on GitHub.

## Documentation continuity outcome (2026-04-07)

- `docs/specs/009-web-draft-kit-ux.md` is the canonical Milestone B web-first UX contract.
- Supporting brainstorm material now lives in `docs/research/002-web-draft-kit-ux-brainstorm.md`.
- Durable architecture decisions now live under `docs/adrs/`, including `007-web-first-draft-session-and-temp-kit-lifecycle.md`.
- Research docs now use their own numbered sequence with `docs/research/INDEX.md` as the folder guide.
- `docs/README.md` now documents folder classification, canonical-source precedence, numbering policy, and the requirement to keep `.agents/axon-state.md` current when docs meaningfully change.

## Backfill/data quality completion status (current)

- Migration `005_hits_blocks_per60` applied to production Supabase project `mrjrtwwmbxfytnnjkaid`
- `scripts/backfill_data_quality.sh` added with staged flow:
  - sample run
  - validation gate
  - full run
  - final validation
- Split historical coverage now enforced operationally:
  - NHL.com raw hits/blocks: `2005-06` onward
  - NST `hits_per60` / `blocks_per60`: `2007-08` onward (NST has no usable rows in `2005-06` and `2006-07`)
- Validation rules now use source-correct TOI checks (non-negative situation TOI values), not `toi_sh < toi_ev`
- Upserts to `player_stats` now use `default_to_null=False` to avoid partial payloads nulling existing columns

## Verified outcomes

- Targeted scraper tests passing after fixes:
  - `pytest tests/scrapers/test_nst.py tests/scrapers/test_nhl_com.py` → 85 passed
- Targeted season reruns completed after upsert fix:
  - NST `2009-10..2009-10`
  - NHL.com `2009-10..2009-10`
  - NHL.com `2024-25..2024-25`
- Season-level DB validation now shows:
  - Raw coverage strong from `2005-06` onward
  - Rate coverage strong from `2007-08` onward, including corrected `2009-10`
  - No negative `toi_ev` / `toi_pp` / `toi_sh` values
  - `2026-27` empty is acceptable because season not started

## Decisions now in force

- NHL.com summary/realtime backfills remain `isAggregate=true`
- NST per-60 historical floor is operationally `2007-08`
- Web draft kit remains primary launch target; extension remains secondary and non-blocking for web launch
- Auth + saved kits remain required launch scope for the web product
- First real ML run should happen immediately after remaining scraper hardening (Hockey Reference dedup) closes

## Execution outcomes (2026-03-29)

- HR targeted verification backfill succeeded (`2009-10..2010-11`, 336 rows).
- First real ML run succeeded for `2026-27` (dataset 11229, artifacts uploaded, `player_trends` 901 rows).
- Trends endpoint now returns stable populated responses with normalization + pagination fixes.

## Execution outcomes (2026-04-01)

- Hockey Reference parser dedup now prefers stable key sources in order: player href id (e.g. `mcdavid01`) → `data-append-csv` → name fallback.
- Added regression test to ensure same-name players with distinct HR ids are not incorrectly deduped in a single season.
- Targeted tests passed:
  - `pytest tests/scrapers/test_hockey_reference.py -v` → 31 passed
  - `pytest tests/scrapers/test_nhl_com.py tests/scrapers/test_nst.py -v` → 85 passed
- One-season data-quality verification passed (`2024-25`):
  - `total=925`, `gp_rows=924`, `rate_rows=914` (`98.9%`), `raw_rows=920` (`99.6%`)
  - No validation failures; TOI non-negativity check passed.

## Merge outcome (2026-04-01)

- PR #30 merged successfully into `main`.
- Canonical status now advances from scraper/backfill closeout into draft-kit workflow/UI scope lock.
