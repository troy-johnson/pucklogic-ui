# Plan: Session-Close Rankings Snapshot

**Spec basis:** `docs/specs/011-milestone-c-token-pass-backend.md`  
**Branch:** `feat/011b-session-close-rankings-snapshot`  
**Risk Tier:** 3 — schema + session lifecycle + ML snapshot correctness  
**Scope:** Medium (~1 day)  
**Execution mode:** Dependency waves  
**Execution status:** Approved on 2026-04-30  
**Readiness:** Ready for implement-tdd  
**Key decisions:** This plan intentionally carries the second half of spec 011's additive schema work: `011a` ships `subscriptions` entitlement columns, while `011b` ships `draft_sessions` recipe/snapshot columns. The split is safe because `snapshot_rankings_at_close` does not exist until `011b` lands.

---

## Goal
Persist the ranking recipe on draft-session start and write a fresh rankings snapshot on clean close for post-season ML comparison.

## Non-Goals
- Cache-backed snapshot reads
- Refund/billing behavior
- Retry-sweep orchestration beyond the approved spec
- Changes to manual fallback semantics outside regression preservation

---

## File Surface

### Created
| File | Change |
|---|---|
| `supabase/migrations/010_session_close_rankings_snapshot.sql` | Add session recipe fields and close-time snapshot column(s) to `draft_sessions` |

### Modified
| File | Change |
|---|---|
| `apps/api/repositories/draft_sessions.py` | Persist recipe inputs at start and snapshot payload at close |
| `apps/api/services/draft_sessions.py` | Use draft-session row as authority for start/resume/close snapshot behavior |
| `apps/api/services/rankings.py` | Provide fresh recompute path used by close-time snapshot |
| `apps/api/routers/draft_sessions.py` | Keep route wiring aligned if service contracts or start payload handling change |
| `apps/api/models/schemas.py` | Add/adjust schema fields only if needed for persisted session recipe inputs |
| `apps/api/tests/repositories/test_draft_sessions.py` | Cover stored recipe inputs and snapshot persistence |
| `apps/api/tests/services/test_draft_sessions.py` | Cover start/reconnect/expiry/manual fallback consistency and close-time snapshot logic |
| `apps/api/tests/services/test_rankings.py` | Cover snapshot recompute path using persisted recipe inputs |
| `apps/api/tests/routers/test_draft_sessions.py` | Cover route-level lifecycle regressions if service behavior surfaces at API level |
| `docs/backend-reference.md` | Document persisted session recipe fields and close-time snapshot semantics |

### Deleted
- None

---

## Implementation Phases
### Phase 1 — Lock failing lifecycle/snapshot coverage
Add tests for persisted recipe fields, clean-close snapshot writes, and regression-preserved session behaviors.

### Phase 2 — Add persistence
Add draft-session migration and repository writes for recipe/snapshot fields.

### Phase 3 — Wire recompute snapshot flow
Use persisted session inputs to recompute rankings on clean close and no-op safely on missing recipe data.

### Phase 4 — Document and verify
Refresh canonical backend docs and run focused lifecycle verification.

## Task List

### Wave 1 — RED coverage
1. **Add failing repository tests for persisted session recipe fields and snapshot writes.**  
   Command: `Edit apps/api/tests/repositories/test_draft_sessions.py`  
   Expected: Tests assert `season`, `league_profile_id`, `scoring_config_id`, `source_weights`, `platform`, and close-time snapshot values are stored on `draft_sessions`.

2. **Add failing service tests for clean-close snapshot success and missing-recipe no-op.**  
   Command: `Edit apps/api/tests/services/test_draft_sessions.py`  
   Expected: Tests assert clean close writes the documented JSON snapshot, missing recipe inputs log a no-op, and snapshot generation does not read cached rankings.

3. **Add failing regression tests for reconnect, expiry, and manual fallback consistency.**  
   Command: `Edit apps/api/tests/services/test_draft_sessions.py and apps/api/tests/routers/test_draft_sessions.py`  
   Expected: Tests assert start/reconnect/expiry/manual fallback behavior remains unchanged and expired/abandoned sessions may keep snapshot as `NULL`.

4. **Add failing rankings-service tests for fresh recomputation from persisted recipe inputs.**  
   Command: `Edit apps/api/tests/services/test_rankings.py`  
   Expected: Tests assert the close-time snapshot path recomputes from stored recipe inputs rather than reusing request cache state.

### Wave 2 — Persistence
5. **Create the draft-session snapshot migration.**  
   Command: `Create supabase/migrations/010_session_close_rankings_snapshot.sql`  
   Expected: Migration additively extends `draft_sessions` with the approved recipe and snapshot fields.

6. **Implement repository support for recipe persistence and snapshot updates.**  
   Command: `Edit apps/api/repositories/draft_sessions.py`  
   Expected: Repository can write recipe fields on start and update snapshot payload on clean close.

7. **Align schemas with persisted recipe inputs if route/service contracts require it.**  
   Command: `Edit apps/api/models/schemas.py`  
   Expected: Schema changes are limited to fields needed for the approved start/close persistence flow.

### Wave 3 — Lifecycle + recompute wiring
8. **Persist recipe inputs when a draft session starts.**  
   Command: `Edit apps/api/services/draft_sessions.py`  
   Expected: Session creation stores `season`, `league_profile_id`, `scoring_config_id`, `source_weights`, and `platform` on the authoritative session row.

9. **Implement the fresh rankings snapshot builder.**  
   Command: `Edit apps/api/services/rankings.py`  
   Expected: Snapshot generation recomputes rankings from persisted recipe inputs and returns the documented JSON shape.

10. **Wire snapshot generation into the clean-close path only.**  
    Command: `Edit apps/api/services/draft_sessions.py`  
    Expected: Clean close writes snapshot data, missing inputs log a no-op, and expiry/abandon paths do not force snapshot creation.

11. **Adjust router wiring only where lifecycle contract exposure requires it.**  
    Command: `Edit apps/api/routers/draft_sessions.py`  
    Expected: API routes remain consistent with the draft-session service authority and do not regress reconnect/manual fallback behavior.

### Wave 4 — Docs + verification
12. **Update canonical backend docs for session recipe persistence and close-time snapshot behavior.**  
    Command: `Edit docs/backend-reference.md`  
    Expected: Docs describe start-time persisted recipe fields, clean-close snapshot semantics, no-op logging on missing inputs, and `NULL` snapshots for expired/abandoned sessions.

13. **Run focused verification for session lifecycle and snapshot behavior.**  
    Command: `python -m pytest apps/api/tests/repositories/test_draft_sessions.py apps/api/tests/services/test_draft_sessions.py apps/api/tests/services/test_rankings.py apps/api/tests/routers/test_draft_sessions.py`  
    Expected: All targeted tests pass with no lifecycle or snapshot regressions.

---

## Verification Mapping
| Acceptance need | Tasks / Covered by |
|---|---|
| `POST /draft-sessions/start` persists season/profile/scoring/source_weights/platform | 1, 5, 6, 8, 13 |
| `snapshot_rankings_at_close` writes documented JSONB snapshot on clean close | 1, 2, 4, 9, 10, 13 |
| Missing recipe inputs log no-op | 2, 10, 13 |
| Expired/abandoned sessions may leave snapshot `NULL` | 3, 10, 12, 13 |
| Snapshot is recomputed, not pulled from cache | 2, 4, 9, 13 |
| Start/reconnect/expiry/manual fallback behavior remains consistent | 3, 8, 10, 11, 13 |

## Risks
- Snapshot correctness depends on the session row being the single source of truth; partial fallback to request-time state would violate the spec.
- Clean-close detection must be explicit; over-triggering snapshot generation could create misleading ML comparison data.
- This plan introduces the second half of the deliberate migration split; implementation should not merge it back into `011a` without first updating the plan.

## Open Questions
1. Which exact lifecycle transition is the sole “clean close” authority? This plan assumes the current explicit successful-close path in `draft_sessions` service.
2. Is a retry sweep for missed snapshots needed later? This plan assumes no, because best-effort close-time write satisfies current acceptance criteria.
