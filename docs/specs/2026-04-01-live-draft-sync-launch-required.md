# Launch-Required Live Draft Sync

**Status:** Draft for approval  
**Date:** 2026-04-01  
**Milestone:** Milestone B — Lock the draft kit workflow / UI scope

## Summary

PuckLogic v1 must support a live, in-draft experience where a user can keep rankings and suggestions synchronized with the actual draft state. Live draft sync is a launch gate, not a stretch feature. The launch experience must remain usable even when automatic draft-room detection is degraded, so manual pick entry and reconnectable session recovery are also required.

## Goals

- Make live draft sync a required launch capability.
- Let a user start or join a draft session and keep PuckLogic synchronized with real draft picks.
- Recompute or refresh rankings/suggestions against current draft state during the draft.
- Preserve a usable draft workflow when automatic sync fails through manual pick entry.
- Recover session state after refresh, reconnect, or extension/browser interruption.

## Non-goals

- Full cross-platform parity if it jeopardizes launch.
- Collaboration or multi-user war-room workflows.
- Advanced commissioner tools or league-history import.
- Mobile-first in-draft UX.
- Perfect automation with no fallback path.

## Launch definition

PuckLogic is not launch-ready unless all of the following are true:

1. A real user can start or resume a live draft session.
2. Picks can be captured and reflected in session state in near real time.
3. Rankings/suggestions update from current draft state.
4. The user can continue via manual pick entry if automatic sync fails.
5. Session state survives reconnects and reloads well enough to continue a real draft.
6. Sync health is visible enough that users know whether the product is still trustworthy mid-draft.

## User stories

- As a drafter, I can connect PuckLogic to my live draft so I do not have to manually track every pick.
- As a drafter, I can see updated rankings/suggestions after each pick.
- As a drafter, I can resume my draft session if my browser reloads or disconnects.
- As a drafter, I can continue drafting with manual entry if automatic sync stops working.
- As a drafter, I can tell when sync is healthy versus degraded.

## Design decisions

### 1. Live draft sync is launch-critical

Live draft sync moves from secondary/stretch scope to required launch scope.

### 2. Manual fallback is also launch-critical

Automatic detection is not enough. If DOM parsing, extension sync, or background worker lifecycle causes issues, the user must still be able to continue the draft via manual pick entry.

### 3. Session-based architecture

Live draft sync is modeled as a persisted `draft_session` with:

- session identity
- user ownership
- platform context
- linked league/profile context where applicable
- current draft state
- drafted players / picks
- sync-health and reconnect metadata

### 4. Realtime transport uses WebSocket state sync

The product uses a WebSocket session model for live updates between extension/client and backend. The backend remains the authoritative source of draft-session state.

### 5. Recovery-first behavior is mandatory

Reconnect and state restoration are required launch behavior because extension and browser lifecycle interruptions are expected.

### 6. Scope must tighten elsewhere

Because live draft sync is now launch-critical, other v1 surfaces must stay constrained:

- keeper support remains lightweight
- advanced league workflows remain bounded
- extension polish beyond the required sync path is secondary

## Scope

### In scope

- create draft session
- join or resume active draft session
- ingest picks from extension
- manual pick entry fallback
- websocket state update flow
- reconnect and `sync_state` recovery
- rankings/suggestions refresh from current draft state
- visible sync state in UI (`connected`, `reconnecting`, `out_of_sync`, `manual_mode`)

### Out of scope

- collaboration or shared draft-room coordination
- auction-draft-specific workflows unless trivial to support
- deep post-draft analytics
- removing manual fallback
- full parity for every platform edge case at launch

## Platform support at launch

### Recommended launch stance

- **Required:** ESPN live draft sync
- **Best effort / conditional:** Yahoo live draft sync
- **Not required:** parity across all supported platforms

### Rationale

Current architecture and risk notes indicate ESPN is the safer launch-critical target. Requiring both ESPN and Yahoo at equal launch quality materially increases schedule risk.

## Functional requirements

### A. Session lifecycle

- User can create a draft session from the web app.
- User can resume an active session after reconnect/reload.
- Session stores enough authoritative state to reconstruct draft progress.
- Session can be explicitly ended or expire safely after inactivity.

### B. Live pick sync

- Extension detects picks from supported draft-room DOM selectors.
- Pick events are sent to the backend session stream.
- Backend validates, deduplicates, and persists accepted picks.
- Connected clients receive updated session state.

### C. Rankings / suggestions refresh

- After each accepted pick, draft state updates.
- PuckLogic refreshes available-player context and recommendations.
- User sees updated rankings/suggestions without losing draft continuity.

### D. Manual fallback

- User can enter picks manually at any time.
- Manual entry is available when:
  - extension is unavailable
  - platform detection fails
  - sync becomes unreliable
- Manual entry writes to the same draft-session state model as automatic pick ingestion.

### E. Recovery / reconnect

- On reconnect, the client or extension requests authoritative server state.
- Backend returns `sync_state` for reconciliation.
- Product can reconcile local UI state against authoritative session state.
- Sync-health state is surfaced clearly to the user.

### F. Auth / entitlement

- Live draft sync requires authenticated access.
- Draft-session ownership and authorization are enforced server-side.
- If paid entitlement is required at launch, entitlement is checked before session start and during reconnect recovery.

## Event and state model

### Required event types

- `pick`
- `sync_state`
- `get_suggestions`
- `suggestions`
- `state_update`
- `error`

### Required session-state concepts

- session id
- user id
- platform
- draft status
- drafted picks / players
- current turn or last processed pick
- sync-health state
- resume or reconnect identifier as needed

### Pick event minimum fields

- player identifier
- pick number or draft position when available
- platform source
- timestamp
- ingestion mode (`auto` or `manual`)
- optional roster/team context when available

## UX requirements

### Draft sync states

The UI must clearly represent:

- connected
- reconnecting
- disconnected
- out of sync
- manual fallback active

### User controls

The user must be able to:

- start live sync
- reconnect or resume a session
- switch to manual mode
- enter a missed pick manually
- review sync health

### Failure handling

If automatic sync confidence drops:

- warn the user
- preserve session continuity
- offer manual pick entry immediately
- avoid silently continuing in a misleading state

## Acceptance criteria

### Launch gate acceptance

- [ ] A real user can start a live draft session and use it during a real draft.
- [ ] Picks can be captured and reflected in session state in near real time.
- [ ] Rankings/suggestions update after accepted picks.
- [ ] Refresh/reconnect does not destroy usable draft continuity.
- [ ] User can continue via manual fallback if automatic sync fails.
- [ ] Sync health is visible in the UI.
- [ ] Server-side auth and ownership checks are enforced.
- [ ] Live draft sync is treated as required launch scope in product planning and implementation.

### Reliability acceptance

- [ ] Reconnect restores authoritative state well enough to continue the draft.
- [ ] Duplicate and missed pick handling are defined and tested.
- [ ] Manual and automatic pick ingestion converge into one consistent session model.
- [ ] DOM volatility or extension interruption does not fully block draft use because fallback exists.

## Risks

- ESPN and Yahoo draft-room DOM churn
- MV3 service worker termination and reconnect timing
- session desync between extension, UI, and backend
- auth/entitlement issues blocking launch-critical flow
- scope blow-up if ESPN and Yahoo are both treated as equal hard requirements immediately

## Resolved questions

- Live draft sync is required for launch.
- Manual fallback is required for launch.
- Session recovery and reconnect are required for launch.
- Live draft sync requires authentication.

## Unresolved questions

1. Is launch approval satisfied by ESPN-only live sync, or must Yahoo also be launch-required?
2. Should paid entitlement be enforced at launch, or is authentication alone enough for early launch scope?
3. How draft-aware must suggestions be at v1: simple best-available versus more roster-aware recommendation logic?
4. What exact sync-latency or user-visible freshness threshold is acceptable during a real draft?

## Recommendation

Approve this spec with the following scope guardrail:

> Launch requires reliable ESPN live draft sync, reconnectable draft sessions, and manual fallback. Yahoo may ship at launch only if it does not jeopardize ESPN stability or session recovery quality.

Do not proceed to planning until this spec is approved.
