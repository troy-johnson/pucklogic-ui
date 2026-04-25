# Plan: Draft Pass Session Lifecycle and Completion Policy

**Spec basis:** `docs/specs/008-live-draft-sync-launch-required.md`, `docs/specs/009-web-draft-kit-ux.md`  
**Branch:** `feat/008d-draft-pass-session-lifecycle`  
**Risk Tier:** 3 — entitlement enforcement, schema migration, reconnect lifecycle  
**Scope:** Medium (~1–2 days, multi-session)  
**Execution mode:** Dependency waves  
**Key decisions:** a draft pass is consumed on first successful session start, reconnect never consumes another pass, closed sessions cannot be resumed onto the same pass  
**Execution status:** Implementation complete on PR #34 (`feat/008d-draft-pass-session-lifecycle`)  
**Readiness:** Approved for merge as of 2026-04-25; launch-readiness still depends on seasonal manual verification

> **Status update — 2026-04-25:** PR #34 is mergeable after the final `/end` terminal-session 409 fix and review-thread reconciliation. Automated coverage now includes pass-consumption invariants, terminal reconnect denial, Stripe pass-credit idempotency, and extension reconnect suppression on `SESSION_CLOSED`. The only remaining launch caveat is the already-documented seasonal manual draft-room verification.

## Launch Decisions

- A draft pass transitions from **available** to **active** on the first successful `POST /draft-sessions/start`.
- Reconnect, websocket attach, resume, manual fallback, and sync recovery **must not consume an additional pass**.
- A pass can back **exactly one active session** at a time.
- A session is considered closed when it reaches one of two launch-scope terminal outcomes:
  - `ended` via explicit user action
  - `expired` via inactivity timeout/grace expiry
- Platform-complete DOM detection and pick-count completion are deferred post-launch (season-blocked verification required).
- Any terminal outcome consumes/closes the pass for reuse protection.
- Inactivity expiry is a fallback close path, not a clean completion signal.
- The backend remains the authoritative source of pass/session linkage and allowed reconnect behavior.

---

## Goal

Define and implement the authoritative pass/session lifecycle so users can safely reconnect to an in-progress live draft without paying twice, while preventing concurrent or repeated draft usage on a single pass.

## Non-Goals

- Billing checkout redesign
- Subscription catalog changes beyond storing a consumable pass/session linkage
- Cross-instance locking beyond launch-time single-instance assumptions
- Full entitlement UI polish
- Multi-draft bundles or reusable pass products

---

## File Surface

| File | Change |
|---|---|
| `supabase/migrations/<new>_draft_session_lifecycle.sql` | Migrate `draft_sessions` to the authoritative session contract |
| `apps/api/models/schemas.py` | Add terminal/completion fields as needed |
| `apps/api/repositories/draft_sessions.py` | Enforce pass/session persistence and close semantics |
| `apps/api/repositories/subscriptions.py` | Add pass lookup / state transition helpers as needed |
| `apps/api/services/draft_sessions.py` | Enforce pass lifecycle invariants and completion policy |
| `apps/api/routers/draft_sessions.py` | Add completion endpoint/event handling as needed |
| `apps/api/tests/repositories/test_draft_sessions.py` | Add migration-contract and persistence tests |
| `apps/api/tests/services/test_draft_sessions.py` | Add lifecycle, reconnect, and anti-abuse tests |
| `apps/api/tests/routers/test_draft_sessions.py` | Add HTTP/WS completion and reconnect tests |
| `docs/backend-reference.md` | Update canonical `draft_sessions` contract |
| `docs/extension-reference.md` | Document completion/reconnect event contract |

### DB / Persistence Changes

The new authoritative `draft_sessions` contract should store at minimum:

- `session_id`
- `user_id`
- `platform`
- `status`
- `entitlement_ref` or equivalent `pass_id`
- `completion_reason` (nullable until terminal)
- `sync_state`
- `accepted_picks`
- `created_at`
- `updated_at`
- `last_heartbeat_at`
- `recovered_at`
- `completed_at` (nullable until terminal)

Launch-time invariants should be enforced by schema and service logic:

- at most one active session per user
- at most one active session per pass
- closed sessions cannot be reactivated by reconnect

---

## Implementation Phases

> The phases and task list below are retained as the executed implementation plan for historical traceability; branch status should be taken from the execution/readiness lines above.

### Phase 1 — State model and migration contract

Define the canonical pass/session state machine and migrate `draft_sessions` to the new shape while preserving launch-time safety. Because Supabase currently has zero `draft_sessions` rows, the migration may optimize for clarity over historical backfill complexity.

### Phase 2 — Pass-link enforcement

Implement server-side linkage between a started draft session and the pass that authorized it. All follow-on lifecycle operations must validate the same linked pass without double consumption.

### Phase 3 — Completion and expiry semantics

Implement terminal state handling for platform-complete, pick-count complete, explicit user end, and inactivity expiry. Each terminal path must close the session and prevent pass reuse.

### Phase 4 — Reconnect and anti-abuse verification

Verify reconnect works with the same active pass/session while blocked second starts, stale reconnects, and race-like repeated start attempts are denied.

---

## Task List

### Wave 1 — schema and state machine

1. **Add failing repository/service tests for pass/session linkage and terminal fields.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/repositories/test_draft_sessions.py apps/api/tests/services/test_draft_sessions.py -k "entitlement or completion or expired or ended or active session" -q`  
   Expected: tests fail because the current schema and repository contract do not fully model pass/session lifecycle.

2. **Create the `draft_sessions` migration for the authoritative lifecycle contract.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/repositories/test_draft_sessions.py -q`  
   Expected: repository tests pass against the new persisted field set.

3. **Update canonical backend docs to match the new `draft_sessions` table shape.**  
   Command: `git diff -- docs/backend-reference.md supabase/migrations`  
   Expected: canonical docs and migration no longer disagree on the launch contract.

### Wave 2 — pass consumption rules

4. **Add failing service tests for first-start consumption vs reconnect non-consumption.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/services/test_draft_sessions.py -k "consume or reconnect or same pass" -q`  
   Expected: tests fail until the service explicitly distinguishes start from reconnect.

5. **Implement pass-link persistence and reuse-safe validation.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/services/test_draft_sessions.py -k "consume or reconnect or same pass" -q`  
   Expected: reconnect resumes the same active session without consuming another pass; blocked second starts do not create additional active sessions.

6. **Add failing test for second concurrent start denial using the same pass/user.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/services/test_draft_sessions.py -k "second start or concurrent" -q`  
   Expected: test fails until the one-active-session / one-active-pass invariant is enforced.

7. **Implement the anti-abuse guardrails.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/services/test_draft_sessions.py -k "second start or concurrent" -q`  
   Expected: duplicate active starts are rejected without consuming another pass.

### Wave 3 — closure and reconnect denial

**Scope note:** Platform-complete DOM detection and pick-count completion are deferred post-launch. Launch terminal paths are explicit user end and inactivity expiry only. No new WS message type from the extension is needed.

8. **Add failing tests for terminal session outcomes writing completion_reason and completed_at.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/services/test_draft_sessions.py -k "user_ended or inactivity_expired or completion_reason or completed_at" -q`  
   Expected: tests fail until both terminal paths write completion_reason and completed_at consistently.

9. **Implement completion audit field persistence on ended and expired paths.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/services/test_draft_sessions.py -k "user_ended or inactivity_expired or completion_reason or completed_at" -q`  
   Expected: both terminal paths close the session and record reason + timestamp.

10. **Add router tests for closed-session reconnect denial.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/routers/test_draft_sessions.py -k "reconnect denied or terminal or closed" -q`  
   Expected: tests fail until reconnect to ended/expired sessions is rejected.

11. **Implement reconnect denial for terminal sessions.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/routers/test_draft_sessions.py -k "reconnect denied or terminal or closed" -q`  
   Expected: WS attach and resume requests to ended/expired sessions are rejected with a clear error.

### Wave 4 — launch verification

12. **Run the focused lifecycle verification suite.**  
   Command: `source apps/api/.venv313/bin/activate && pytest apps/api/tests/repositories/test_draft_sessions.py apps/api/tests/services/test_draft_sessions.py apps/api/tests/routers/test_draft_sessions.py -q`  
   Expected: all draft-session lifecycle tests pass.

13. **Manual draft-room verification — deferred (seasonal blocker).**  
   Real ESPN/Yahoo live draft-room verification requires an active draft season and is not possible in the off-season. This step is explicitly deferred until a live draft environment is available. This branch is approved for implementation correctness; launch-readiness remains blocked on seasonal manual verification.  
   See known limitations note below.

---

## Known Limitations

**Real ESPN/Yahoo draft-room verification is deferred until draft season due to environment availability.**  
This branch is approved for implementation correctness; launch-readiness remains blocked on seasonal manual verification.

The following lifecycle paths are covered by automated tests only and have not been exercised against a live draft room:
- Session start → WS attach → manual pick ingestion
- Reconnect and sync_state recovery after disconnect
- Terminal denial (closed session) preventing reconnect
- Extension reconnect suppression on terminal denial

Manual verification evidence must be recorded before promoting to production when a live draft environment is available.

---

## Verification Mapping

| Acceptance need | Tasks |
|---|---|
| Start consumes pass exactly once | 4, 5, 12, 13 |
| Reconnect does not consume another pass | 4, 5, 10, 12, 13 |
| One active session per user/pass | 6, 7, 12 |
| Closed sessions cannot reconnect | 8, 9, 10, 11, 12 |
| Completion reasons are explicit and auditable | 8, 9, 11, 12 |
| Canonical schema/docs match implementation | 2, 3, 12 |

---

## Risks

- Subscription/pass data model may not yet expose a clean consumable-pass primitive, forcing temporary linkage logic.
- Completion by expected pick count requires trustworthy draft-size metadata; if unavailable, platform-complete and explicit end must remain primary.
- Schema migration touches a table protected by RLS and constraints; policy/index updates must stay aligned.
- Reconnect semantics can drift if extension transport and backend terminal states are not updated together.

## Open Questions

1. Should `ended` and `expired` both consume the pass identically at the entitlement layer, or should reporting distinguish them only for analytics/support?
2. ~~Do we already have a stable `pass_id` / entitlement row identity in `subscriptions`, or does launch require a temporary entitlement reference strategy?~~ **Resolved:** `subscriptions` is a simple active/inactive row with no consumable pass primitive. `entitlement_ref` stores the subscription `id` as an audit reference on session start. No pass token table needed for launch.
3. ~~Is expected total pick count available from launch-time league metadata, or should `pick_count_complete` remain optional behind platform support?~~ **Resolved:** `DraftSessionStartRequest` only carries `platform` — no league profile or team count is available at session start. Pick-count completion deferred post-launch alongside platform-complete DOM detection.
4. ~~Should platform-complete arrive as a websocket event, an HTTP call, or both for redundancy?~~ **Resolved:** Platform-complete DOM detection deferred post-launch (season-blocked). Launch terminal paths are user-explicit end and inactivity expiry only. No new extension WS message type needed.
