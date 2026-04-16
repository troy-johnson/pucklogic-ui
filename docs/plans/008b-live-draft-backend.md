# Plan: Live Draft Backend Authority and Realtime Session Flow

**Spec basis:** `docs/specs/008-live-draft-sync-launch-required.md`, `docs/specs/009-web-draft-kit-ux.md`  
**Branch:** `feat/live-draft-sync-backend-contract`  
**Risk Tier:** 3 — Auth, entitlement, session state, realtime transport  
**Scope:** Large (~2–4 days, multi-session)  
**Execution mode:** Dependency waves  
**Transport decision:** WebSocket in the final implementation from the first backend slice

**Execution status (2026-04-15):** Implemented on the current branch, PR-review hardening is incorporated, and the branch is merge-ready pending final PR disposition.
**Readiness:** Ready to merge. Follow-on lifecycle hardening moved to `008d` and is not required for `008b` closure.

**Completion note:** The current branch ships the draft-session API surface, authoritative session persistence, websocket sync transport, browser-compatible query-token websocket auth, manual-pick fallback with player-identity convergence, Supabase schema alignment, and backend reference updates. Verification passed with the focused draft-session backend suite (`87 passed`).

## Infrastructure Decision

- **Launch host:** Fly.io
- **Launch topology:** single FastAPI instance
- **Realtime transport:** WebSocket primary, HTTP for session bootstrap and manual fallback actions
- **Redis:** explicitly deferred as a live-sync dependency until scaling or background-job needs require it
- **Scaling trigger:** add Redis and cross-instance fanout only when live draft traffic or operational needs justify multiple API replicas
- **Platform boundary:** ESPN is launch-critical; Yahoo support must remain feature-gated and non-blocking until proven stable

---

## Goal

Ship the launch-critical backend contract for live draft sync: one authoritative draft session per user, paid launch gating, WebSocket session updates, reconnect via `sync_state`, and manual pick ingestion that converges into the same session model as automatic picks.

## Non-Goals

- Yahoo or ESPN DOM parsing logic
- Final web UI polish
- Multi-user collaborative draft rooms
- Archive/history UX beyond what the API needs to safely resume or end a session
- Promoting Yahoo to equal launch-readiness scope with ESPN

---

## File Surface

| File | Change |
|---|---|
| `apps/api/models/schemas.py` | Add draft-session request/response/event schemas |
| `apps/api/core/dependencies.py` | Add repository/service dependency providers |
| `apps/api/main.py` | Register draft-session router |
| `apps/api/repositories/subscriptions.py` | Add launch entitlement read path needed by session start guard |
| `apps/api/routers/stripe.py` | Align purchase metadata or entitlement writes with draft-session launch gate |
| `apps/api/routers/draft_sessions.py` | Create HTTP + WebSocket API surface |
| `apps/api/repositories/draft_sessions.py` | Create persistence layer for sessions, picks, and sync state |
| `apps/api/services/draft_sessions.py` | Create session lifecycle, dedupe, reconciliation, and pass-consumption logic |
| `apps/api/tests/models/test_schemas.py` | Add draft-session schema tests |
| `apps/api/tests/repositories/test_draft_sessions.py` | Add repository coverage |
| `apps/api/tests/services/test_draft_sessions.py` | Add service coverage |
| `apps/api/tests/routers/test_draft_sessions.py` | Add endpoint + websocket contract coverage |

**Expected database work inside this plan**

- Add `draft_sessions` persistence
- Add session pick/event persistence
- Add durable fields required for reconnect and sync-health state
- Add whichever entitlement fields are required to enforce a per-session paid launch gate

---

## Implementation Phases

### Phase 1 — Schema and repository contract

Establish the request/response/event types first, then the persistence contract for active-session lookup, session create/resume/end/expiry, pick append, and `sync_state` retrieval.

### Phase 2 — Service authority rules

Implement business rules in one place:

- one active session per user
- ESPN required and Yahoo allowed only as a secondary, feature-gated platform
- manual and automatic picks write into the same model
- duplicate pick suppression
- reconnect returns authoritative `sync_state`
- session state transitions own sync-health semantics
- inactivity expiry is enforced safely and does not consume an additional pass on valid reconnect

### Phase 3 — API and WebSocket transport

Expose HTTP endpoints for create/resume/end/manual-pick flows and a WebSocket channel for live session updates and reconnect synchronization.

### Phase 4 — Entitlement enforcement

Apply launch-paid access checks at session start and reconnect using the draft-pass model. A start attempt must fail cleanly when entitlement is missing, a blocked second-session start must not consume a pass, and reconnect must revalidate ownership/entitlement without re-consuming a pass.

### Phase 5 — Verification hardening

Run focused tests for lifecycle, expiry, dedupe, reconciliation, manual fallback, and websocket payload shape.

### Phase 6 — Launch observability baseline

Before shipping realtime, add enough logging and counters to debug connection churn, reconnect loops, attach failures, fallback activation, and desync recovery on a single Fly.io instance.

---

## Historical Task List

### Wave 1 — contract and persistence

1. **Add failing schema tests for draft-session models.**  
   Command: `python -m pytest tests/models/test_schemas.py -k draft_session`  
   Expected: tests fail because the draft-session schemas do not exist yet.

2. **Implement draft-session schemas in `apps/api/models/schemas.py`.**  
   Command: `python -m pytest tests/models/test_schemas.py -k draft_session`  
   Expected: draft-session schema tests pass.

3. **Add failing repository tests for create/get-active/resume/end flows.**  
   Command: `python -m pytest tests/repositories/test_draft_sessions.py`  
   Expected: tests fail because the repository does not exist yet.

4. **Implement `apps/api/repositories/draft_sessions.py`.**  
   Command: `python -m pytest tests/repositories/test_draft_sessions.py`  
   Expected: repository tests pass for session lifecycle and pick persistence.

5. **Add failing repository tests for inactivity expiry and resumability boundaries.**  
   Command: `python -m pytest tests/repositories/test_draft_sessions.py -k expiry`  
   Expected: tests fail because expiry behavior is not implemented yet.

6. **Implement inactivity expiry persistence and resume lookup rules.**  
   Command: `python -m pytest tests/repositories/test_draft_sessions.py -k expiry`  
   Expected: expiry tests pass and active-session queries no longer return expired sessions.

### Wave 2 — authority rules

7. **Add failing service tests for one-active-session, dedupe, and `sync_state`.**  
   Command: `python -m pytest tests/services/test_draft_sessions.py`  
   Expected: tests fail because the service does not exist yet.

8. **Implement `apps/api/services/draft_sessions.py`.**  
   Command: `python -m pytest tests/services/test_draft_sessions.py`  
   Expected: service tests pass for session authority rules.

9. **Add failing service tests for manual pick ingestion convergence.**  
   Command: `python -m pytest tests/services/test_draft_sessions.py -k manual`  
   Expected: manual-ingestion tests fail until the service merges manual and automatic paths.

10. **Implement manual-pick ingestion in the same session-state path as automatic picks.**  
   Command: `python -m pytest tests/services/test_draft_sessions.py -k manual`  
   Expected: manual-ingestion tests pass.

11. **Add failing service tests for expiry enforcement and reconnect without pass re-consumption.**  
    Command: `python -m pytest tests/services/test_draft_sessions.py -k "expiry or reconnect"`  
    Expected: tests fail until expiry and reconnect rules are fully enforced.

12. **Implement expiry enforcement and reconnect entitlement revalidation rules.**  
    Command: `python -m pytest tests/services/test_draft_sessions.py -k "expiry or reconnect"`  
    Expected: reconnect/expiry tests pass and no reconnect path consumes an additional pass.

### Wave 3 — API and websocket

13. **Add failing router tests for create/resume/end/manual-pick endpoints.**  
   Command: `python -m pytest tests/routers/test_draft_sessions.py -k "create or resume or end or manual"`  
   Expected: tests fail because the router does not exist yet.

14. **Implement `apps/api/routers/draft_sessions.py` and register it in `apps/api/main.py`.**  
   Command: `python -m pytest tests/routers/test_draft_sessions.py -k "create or resume or end or manual"`  
   Expected: HTTP lifecycle tests pass.

15. **Add failing router tests for WebSocket connect/reconnect and `sync_state` payloads.**  
   Command: `python -m pytest tests/routers/test_draft_sessions.py -k websocket`  
   Expected: websocket contract tests fail.

16. **Implement WebSocket session transport and reconnect reconciliation.**  
   Command: `python -m pytest tests/routers/test_draft_sessions.py -k websocket`  
   Expected: websocket contract tests pass.

### Wave 4 — entitlement gate

17. **Add failing tests for draft-pass entitlement checks and blocked second-session starts.**  
   Command: `python -m pytest tests/routers/test_draft_sessions.py -k pass`  
   Expected: tests fail because launch gating is not enforced yet.

18. **Implement entitlement enforcement in session start/reconnect paths.**  
   Command: `python -m pytest tests/routers/test_draft_sessions.py -k pass && python -m pytest tests/repositories/test_subscriptions.py`  
   Expected: pass-gating tests pass and subscription repository behavior remains green.

19. **Align Stripe checkout metadata or entitlement writes with draft-session launch gating.**  
   Command: `python -m pytest tests/routers/test_stripe.py tests/routers/test_draft_sessions.py -k pass`  
   Expected: checkout/webhook tests and session gate tests both pass against the same entitlement model.

### Wave 5 — focused verification

20. **Run the focused backend suite for draft sessions.**  
   Command: `python -m pytest tests/models/test_schemas.py tests/repositories/test_draft_sessions.py tests/services/test_draft_sessions.py tests/routers/test_draft_sessions.py`  
   Expected: all draft-session backend tests pass.

21. **Run a manual verification pass against a real-draft-like session flow.**  
    Command: document a manual verification checklist/result in the active PR or continuity notes  
    Expected: evidence exists for create → attach → pick ingestion → reconnect → manual fallback → resume/end behavior.

### Wave 6 — observability and launch posture

22. **Add failing tests for draft-session observability hooks around connect/reconnect/fallback events.**  
   Command: `python -m pytest tests/services/test_draft_sessions.py -k observability`  
   Expected: tests fail because observability events are not emitted yet.

23. **Implement structured logging and counters for socket attach, reconnect, manual fallback, and sync recovery.**  
   Command: `python -m pytest tests/services/test_draft_sessions.py -k observability`  
   Expected: observability tests pass and realtime events emit consistent metadata.

---

## Verification Mapping

| Acceptance need | Covered by |
|---|---|
| User can start a live draft session | Tasks 9–10, 13–15 |
| Resume after reconnect/reload | Tasks 7–8, 15–16, 18 |
| Backend session is authoritative | Tasks 3–8 |
| Manual fallback uses same session model | Tasks 9–10 |
| Duplicate/missed pick handling defined | Tasks 7–8 |
| Session expiry is defined and enforced | Tasks 5–6, 11–12 |
| Sync health / `sync_state` contract exists | Tasks 15–16 |
| Paid entitlement enforced | Tasks 17–19 |
| Manual real-draft-like validation exists | Task 21 |
| Launch observability for realtime debugging | Tasks 22–23 |

---

## Risks

- **Entitlement migration risk:** current backend uses a generic `subscriptions` row and Stripe checkout for `draft_kit`; plan execution must align this with the draft-pass model without breaking existing checkout flows.
- **Single-instance launch constraint:** this is acceptable at launch scale, but realtime behavior must not quietly assume multi-replica fanout exists.
- **WebSocket lifecycle:** reconnect semantics need explicit state ownership; otherwise web and extension clients can diverge.
- **Platform creep:** Yahoo readiness must not expand launch scope or weaken ESPN recovery quality.
- **Schema reversibility:** session and event tables are straightforward to add but harder to undo once clients depend on them.

## Open Questions

1. Should launch-paid access be represented as a durable pass ledger or as an extension of the current subscription row model?
2. What inactivity timeout should expire an abandoned session at launch?
3. Should Yahoo session creation be allowed from day one in the same API, or gated behind supported-platform feature flags until adapter readiness is proven?
