# 2026-04-10 — Live Draft Session Backend and Sync Contract

**Status:** Approved
**Milestone:** B / I — Canonical live draft backend + extension contract
**Priority:** Launch gate
**Risk:** High
**Branch:** `feat/live-draft-sync-spec`
**Supersedes:** the previous `008` draft for all non-UI live draft scope.
**Defers to:** `docs/specs/009-web-draft-kit-ux.md` for product workflow, web UX, entitlement UX, and user-facing state behavior; `docs/specs/010-web-ui-wireframes-design.md` for layouts, wireframes, and design-system details.

## Architecture References

- `docs/pucklogic-architecture.md`
- `docs/backend-reference.md`
- `docs/extension-reference.md`
- `docs/plans/008b-live-draft-backend.md`
- `docs/plans/008c-extension-sync-adapters.md`
- `.agents/axon-state.md`

## Why this spec exists

Spec `009` now owns the canonical web-first product workflow and UX contract. Spec `010` owns the wireframe and layout layer. What remains launch-critical is the non-UI contract that lets those surfaces work safely during a real draft:

- backend-owned authoritative draft sessions
- realtime sync transport and recovery semantics
- extension responsibilities for draft-room observation and event emission
- manual fallback convergence into the same session model
- entitlement enforcement at session boundaries
- verification and observability required to trust the system at launch

This spec is therefore the canonical source for live draft backend and sync behavior. It should be stable enough for implementation planning without reopening web UX scope.

## Goals

- Define the authoritative backend contract for live draft sessions.
- Define the extension-to-backend sync responsibilities required for ESPN-first launch readiness.
- Ensure automatic and manual pick ingestion converge into one durable session model.
- Require reconnect and `sync_state` recovery semantics as part of the core feature.
- Require enough verification and observability to support real-draft launch usage.

## Non-Goals

- Web workflow details, user journeys, or screen states already covered by `009`.
- Wireframes, app shell, layout treatment, or design-system decisions covered by `010`.
- Multi-user collaboration, shared war rooms, or commissioner controls.
- Cross-instance realtime fanout for launch scale.
- Yahoo launch parity if it increases risk to ESPN readiness.

## Delegation Boundary

### Owned by this spec

- backend session authority
- session lifecycle and persistence
- websocket and reconnect contract
- extension sync responsibilities
- manual ingestion convergence rules
- entitlement enforcement at session boundaries
- observability and verification requirements

### Explicitly owned by `009`

- user journeys and product workflow
- start/resume/manual fallback UX
- sync-health meaning from the user's perspective
- draft pass purchase UX and entitlement messaging
- session-end and post-draft product flows

### Explicitly owned by `010`

- live draft screen layout
- sync indicator presentation
- manual pick UI placement
- reconnect banners/modals/patterns
- app shell, workspace, and responsive layout decisions

## Design Decisions

### D1. Live draft backend authority is a launch gate

The launch bar is not just “some live draft UI exists.” Launch requires a backend session authority that can survive reconnects, interruptions, and selector failures.

**Rationale:** UI alone cannot safely own draft continuity.

### D2. Backend session state is authoritative

Each active draft runs through a backend-owned `draft_session`. Web and extension clients send events to, and recover state from, that authority.

**Rationale:** This is required for dedupe, recovery, and trustable cross-surface consistency.

### D3. WebSocket is the primary realtime transport

HTTP is used for session bootstrap and manual fallback actions. WebSocket is the primary transport for live session updates and reconnect synchronization.

**Rationale:** This yields the best realtime UX while keeping manual/bootstrap paths simple.

### D4. Manual fallback is required and writes to the same state model

Manual pick entry is not a separate mode with separate data semantics. It is an alternate ingestion path into the same authoritative draft session.

**Rationale:** This keeps recovery, dedupe, and session continuity coherent.

### D5. ESPN is launch-critical; Yahoo is secondary

ESPN support is required for launch readiness. Yahoo is allowed only if it does not increase delivery risk or weaken recovery quality for ESPN.

**Rationale:** Platform scope must stay reversible and risk-bounded.

### D6. Launch infra optimizes for control, not multi-instance scale

Launch assumes a single FastAPI instance on Fly.io, WebSocket primary transport, HTTP/manual fallback, and Redis deferred until scale or operational needs justify it.

**Rationale:** Expected launch traffic does not justify cross-instance complexity yet.

### D7. Live draft sessions require authentication and paid entitlement

Users must be authenticated. Session start must enforce a paid draft-pass entitlement. Reconnect revalidates entitlement and ownership but does not re-consume a pass.

**Rationale:** The product model is per-session paid access, and reconnect must be reversible.

## System Contract

## Session lifecycle

A draft session must support:

- create
- attach / open live transport
- resume after reconnect or refresh
- accept automatic picks
- accept manual picks
- end explicitly
- expire safely after inactivity

The system must enforce one active session per user unless a future spec changes that rule.

## Draft session state

At minimum, authoritative state must include:

- `session_id`
- `user_id`
- `platform`
- `status`
- entitlement or pass linkage sufficient for audit and reconnect checks
- accepted picks and enough metadata to reconstruct order
- last processed pick or equivalent cursor
- sync-health state used by clients
- timestamps for create/update/heartbeat/recovery purposes

## Required event types

- `pick`
- `sync_state`
- `state_update`
- `error`

Optional but expected follow-on event types, if the recommendation engine is wired into the live session path during launch, include:

- `get_suggestions`
- `suggestions`

## Pick event minimum fields

- player identifier or stable player lookup payload
- pick number or draft position when available
- platform source
- timestamp
- ingestion mode: `auto` or `manual`
- optional team / roster context when available

## Platform responsibilities

### Backend responsibilities

- create, resume, and end authoritative sessions
- validate ownership and entitlement
- validate and dedupe incoming picks
- persist accepted picks and session state
- publish `state_update` and `sync_state` payloads
- expose manual-ingestion API into the same session model
- surface enough observability for attach, reconnect, fallback, and recovery debugging

### Extension responsibilities

- detect supported draft-room context
- extract picks from supported selectors
- emit pick events with platform metadata
- reconnect with backoff and request authoritative `sync_state`
- degrade to manual fallback when selectors or lifecycle behavior become unreliable

### Web responsibilities under this contract

The web app is a client of backend authority. It may bootstrap sessions, open transport, and submit manual picks, but this spec does not define user-facing workflow or visual behavior. That remains in `009` and `010`.

## Required Behavior

### Session lifecycle

- User can create a draft session.
- User can resume an active session after reconnect or reload.
- Session state is durable enough to reconstruct draft progress.
- Explicit end and safe inactivity expiry are both supported.

### Live pick sync

- Extension-detected picks are sent to the backend session stream.
- Backend validates, deduplicates, and persists accepted picks.
- Clients can recover the latest authoritative state after interruption.

### Manual fallback convergence

- Manual pick ingestion is always available through the same session contract.
- Manual and automatic pick ingestion produce the same persisted pick/event shape after normalization.
- Duplicate and missed-pick handling must be defined against one shared state model.

### Recovery and reconnect

- Reconnect requests authoritative session state.
- Backend returns `sync_state` sufficient to continue drafting.
- Reconnect does not strand the user if the extension or browser is interrupted.

### Suggestions integration boundary

This spec requires that accepted picks can drive updated draft-state-aware rankings or suggestions, but it does not define the UI or presentation of those outputs. UI behavior belongs to `009` and `010`.

## Acceptance Criteria

### Backend / session acceptance

- [x] Draft-session ownership and auth checks are enforced server-side.
- [x] Session start enforces paid draft-pass entitlement.
- [x] Reconnect revalidates entitlement/ownership without consuming an additional pass.
- [x] One active session per user is enforced.
- [x] Reconnect restores authoritative session state well enough to continue drafting.
- [x] Duplicate and missed pick handling are defined against the authoritative session model.
- [x] Manual and automatic pick ingestion converge into one session model.

### Transport / recovery acceptance

- [x] WebSocket transport supports live session updates for an active draft session.
- [x] `sync_state` recovery semantics are implemented and testable.
- [x] HTTP/manual fallback actions remain usable if live sync transport is degraded.
- [ ] Extension interruption does not permanently strand the session.

### Platform acceptance

- [ ] ESPN live draft sync is launch-ready.
- [ ] Yahoo remains gated behind non-blocking launch criteria unless explicitly promoted later.
- [ ] Selector failures do not fully block draft use because manual fallback exists.

### Verification and observability acceptance

- [x] Automated tests cover draft-session lifecycle and pick-state reconciliation.
- [x] Automated tests cover duplicate and missed pick handling.
- [x] Automated tests cover manual pick ingestion.
- [x] Automated tests cover reconnect and `sync_state` recovery semantics.
- [x] Structured logging or counters exist for socket attach/open/close, reconnect attempts, manual fallback activation, and sync recovery/desync events.
- [ ] Manual verification proves the backend/extension flow is usable in a real draft-like session.

## Risks and Guardrails

- **DOM churn:** selectors will break over time; recovery must degrade to manual mode instead of failing hard.
- **MV3 lifecycle:** service-worker interruption is expected and must be handled as a core flow.
- **Desync risk:** authority, dedupe, and recovery cannot be split across multiple sources of truth.
- **Reversibility:** Redis and multi-instance fanout are explicitly deferred to keep launch architecture reversible.
- **Entitlement edge cases:** reconnect must not accidentally consume multiple passes or orphan a paid session.

## Resolved Questions

- Live draft backend authority is required for launch.
- WebSocket is the primary realtime transport.
- Manual fallback is required for launch.
- ESPN is the minimum launch-critical platform.
- Launch infra is single-instance Fly.io with Redis deferred.
- Draft-pass entitlement is the launch access model.

## Open Questions

1. Should live suggestions at v1 be simple best-available output or roster-aware recommendations derived from the same state update path?
2. What inactivity timeout should expire an abandoned draft session at launch?
3. Should Yahoo remain hidden behind a feature flag in the same API surface, or behind a separate readiness gate until adapters are proven?

## Recommendation

Treat this as the canonical non-UI contract for live draft implementation. Use `009` for UX/product decisions, `010` for wireframes, and `008b` / `008c` for implementation sequencing.
