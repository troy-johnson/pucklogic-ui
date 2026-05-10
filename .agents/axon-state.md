⚠️ **LEGACY STATE FILE — migrated to `docs/state/workflow-state.md` on 2026-05-05**

| Field | Value |
|---|---|
| Active Phase | `idle` — Milestone D complete |
| Active Branch | `main` |
| Open PR | None — PR #37 merged 2026-05-10 |
| Current Focus | Milestone E — export polish (scope TBD) |
| Track | N/A — between tracks |
| Last Action | 2026-05-10: merged PR #37 (Milestone D web draft kit UI) to main; post-merge doc reconciliation |
| Next Session Entry | See `docs/state/workflow-state.md` |

## Milestone D implementation outcome (2026-05-09 → 2026-05-10)

- Implemented all 5 waves of plan `010a` on `feat/milestone-d-web-ui`: design-token baseline (c6b78e4), shell + landing + middleware + auth layout (a38c6f9), pre-draft workspace + kits + auth pages (6e0ec19), draft-session API + slice + StartDraftModal (fe888eb), live draft screen + manual pick drawer + reconnect banner (190460d).
- All 23 AC items green; 182 tests passing across 26 files; production build exits 0 with routes `/`, `/auth/callback`, `/dashboard`, `/live`, `/login`, `/signup`.
- PR #37 opened against `main`; CI green (Backend tests, Frontend tests, Vercel preview).
- Four review rounds resolved; full audit trail in `docs/plans/010a-adversarial-review-r1.md`:
  - PR/QA round 1 (self-review) fixed in c96f56d + 235c09b: live route hydration, StartDraftModal entry point, cookie hardening, KitSwitcher real dropdown, kitId hydration.
  - PR/QA round 2 (external review) fixed in c44bf4f: real ranked players on /dashboard and /live, KitContextSwitcher kit loading, entitlement error logging, end-draft cookie cleanup, user-kits token-auth tests.
  - PR/QA round 3 (deferred minors) fixed in ba8bfa9: token consistency, `?next=` redirect, callback error logging, KitSwitcher name collision.
  - PR/QA round 4 (Codex) C-1 already resolved in c44bf4f; C-2 (ManualPickDrawer stale defaults) fixed in 8e301ba.
- Adversarial PR/QA coverage on auth-surface files (`middleware.ts`, `(auth)/layout.tsx`, `auth/callback/route.ts`, `StartDraftModal.tsx`) complete per plan ship-gate requirement.

## Merge and code review outcome (2026-04-10)

- PR #32 (`feat/live-draft-sync-backend-contract`) has now been merged to `main`, so `008b` is complete and no merge-ready PR remains open for that track.
- Active execution focus shifts to `008c-extension-sync-adapters`, with branch creation deferred until the remaining spec/plan details and stale contract references are reconciled.

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
- Activated execution sequence on 2026-04-11: `008b` is the first implementation track, `008c` follows backend protocol stabilization, and `010a` is restricted to scaffold work until spec `010` leaves draft. As of 2026-04-18, `008b` is complete on `main` and `008c` is the active next track.
- Reviewed and approved spec `docs/specs/011-milestone-c-token-pass-backend.md` for implementation after resolving entitlement, export, and snapshot-source doc conflicts.
- Wrote implementation plan `docs/plans/011a-token-pass-entitlements-and-gating.md` for Stripe kit-pass purchase flow, authenticated entitlement reads, gated routes, and roadmap/docs alignment.
- Wrote implementation plan `docs/plans/011b-session-close-rankings-snapshot.md` for persisted draft-session recipe inputs and clean-close rankings snapshot generation.
- Updated `docs/plans/INDEX.md` to index `011a` and `011b` as approved plans.
- Locked Milestone C execution order on 2026-04-30: `011a` runs first for `subscriptions` entitlement columns, Stripe product/webhook handling, `GET /entitlements`, and route gating; `011b` follows for `draft_sessions` recipe/snapshot columns and close-time rankings snapshots.
- Executed `011a` implement-tdd through entitlement storage/read paths, Stripe metadata/webhook credit behavior, route gating (`user-kits`, `league-profiles`, `exports`), dependency coverage, docs updates, and focused verification.
- Executed `011b` implement-tdd through recipe persistence schema alignment, close-time snapshot repository/service wiring, rankings recompute snapshot builder integration, backend docs updates, and plan-specified focused verification command.

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

## Documentation taxonomy update (2026-04-19)

- `docs/README.md` now explicitly distinguishes the roles of `docs/ROADMAP.md`, `docs/pucklogic-architecture.md`, and the top-level backend/frontend/extension reference docs.
- `ROADMAP.md` is treated as the milestone sequencing / launch-prioritization layer, not the canonical source for technical behavior.
- `pucklogic-architecture.md` remains the cross-system blueprint, while the surface reference docs remain the canonical implementation references for their respective domains.
- `docs/ROADMAP.md` was refreshed to match current execution reality: first real ML execution is complete, Milestone B scope approval landed early, `008b` is complete on `main`, `008c` is the active implementation track, and `010a` remains scaffold-only pending spec `010` approval.
- Targeted consistency updates reconciled stale export-flow, route, extension-runtime, and active-PR wording across `docs/pucklogic-architecture.md`, `docs/frontend-reference.md`, `docs/extension-reference.md`, `docs/plans/008c-extension-sync-adapters.md`, and the top axon-state summary.
- `docs/ROADMAP.md` now tracks blocked/pre-launch follow-ups for season-based live draft-room verification, backend-owned inactivity-timeout confirmation, and analytics/metrics planning; `docs/extension-reference.md` and `docs/plans/008c-extension-sync-adapters.md` now link those items as out-of-scope follow-ups rather than unfinished runtime implementation.
- Notion task state was reconciled for the most relevant live-draft/extension cards: WebSocket draft session management, ESPN adapter, and Yahoo adapter now reflect implemented runtime work plus season-blocked verification; the popup/session-activation card remains backlog but now points to the current draft-session API model.
- Second-pass Notion cleanup updated additional extension cards: MV3 scaffold is marked done; sidebar overlay and richer live suggestions remain backlog with current-scope notes; beta testing is marked blocked on season availability; Chrome Web Store submission remains backlog with updated launch-readiness dependencies.
- `docs/README.md` now explicitly states Notion's role versus repo docs: Notion is for project-management/status tracking, `ROADMAP.md` is the repo milestone-priority layer, repo docs remain canonical for technical behavior, and `.agents/axon-state.md` remains the current-session tracker.
- `docs/README.md` now also contains explicit agent instructions for when to update repo docs, `.agents/axon-state.md`, and Notion, including a required end-of-session sync checklist and minimum sync expectations by change type.

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
