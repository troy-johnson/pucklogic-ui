# 2026-04-01 — Live Draft Sync Launch Requirement

**Status:** Draft for approval
**Milestone:** B — Lock the draft kit workflow / UI scope
**Priority:** Launch gate
**Risk:** High
**Branch:** `feat/live-draft-sync-spec`
**Superseded by:** `docs/specs/009-web-draft-kit-ux.md` for web-first UX workflow, screen, and design-system planning. This spec remains relevant for the live-draft-sync launch requirement and recovery/fallback constraints.

## Architecture References

- `docs/pucklogic-architecture.md`
- `docs/backend-reference.md`
- `docs/extension-reference.md`
- `docs/plans/008a-draft-season-readiness.md`
- `.agents/axon-state.md`

## Why this spec exists

The current readiness plan treats the extension and live draft sync as secondary unless they can be shipped safely. Product direction has now changed: **live draft sync is required for launch**. That changes launch scope, risk allocation, and implementation order.

This spec defines the launch bar for live draft sync, the minimum supported workflow, the required recovery/manual fallback behavior, and the constraints needed to keep the scope buildable.

## Goals

- Make live draft sync a required launch capability.
- Let a user start or resume a draft session and keep PuckLogic synchronized with real draft picks.
- Refresh rankings/suggestions from current draft state during an active draft.
- Preserve draft usability via manual pick entry when automatic sync degrades.
- Recover draft-session state after refresh, reconnect, or extension/browser interruption.

## Non-Goals

- Full cross-platform parity if it jeopardizes launch.
- Collaboration or multi-user war-room workflows.
- Advanced commissioner tools or league-history imports.
- Mobile-first in-draft UX.
- Perfect automation with no manual fallback path.

## Launch Workflow

The launch-required in-draft workflow is:

1. Authenticated user starts a live draft session from the web app.
2. User connects extension-backed sync for a supported draft room.
3. Picks flow into the authoritative backend session state in near real time.
4. Rankings/suggestions refresh after accepted picks.
5. If sync becomes unreliable, the user switches to manual pick entry without losing session continuity.
6. If the browser/extension disconnects, the user can resume the session and reconcile state.

PuckLogic is not launch-ready unless this workflow is reliable enough for a real draft.

## Design Decisions

### D1. Live draft sync is a launch gate

Live draft sync is required launch scope, not a stretch feature or post-launch enhancement.

**Rationale:** Product direction now treats the in-draft experience as part of the core launch promise.

### D2. Manual fallback is also launch-required

Manual pick entry must be available whenever automatic detection is missing, degraded, or unreliable.

**Rationale:** ESPN/Yahoo DOM volatility and MV3 lifecycle behavior make a no-fallback design too risky for real draft usage.

### D3. Backend session state is authoritative

Draft state must be persisted in a backend-owned `draft_session`; extension and web UI are clients of that state, not alternate sources of truth.

**Rationale:** Reconnect, dedupe, recovery, and multi-surface consistency all depend on a single authority.

### D4. Reconnect and sync recovery are part of the core feature

Reconnect behavior, `sync_state` reconciliation, and visible sync-health status are required launch behaviors.

**Rationale:** Extension/service-worker interruptions are expected, not exceptional.

### D5. ESPN is the launch-critical platform target

ESPN live draft sync is the minimum required platform for launch approval. Yahoo may ship at launch only if it does not jeopardize ESPN stability or recovery quality.

**Rationale:** Existing repo docs and risk notes indicate ESPN is the safest primary target.

### D6. Auth is required for live draft sync

Live draft sync requires authenticated access. If paid entitlement is enforced at launch, entitlement checks occur before session start and on reconnect.

**Rationale:** Draft sessions are persistent, user-owned state and must be protected server-side.

## Implementation Surface

The implementation implied by this spec will touch at least these surfaces:

- **Backend API**
  - draft session creation/resume endpoints
  - websocket draft-session transport
  - pick validation, dedupe, persistence, and state broadcast
- **Web app**
  - draft session entry/start UI
  - sync-health UI states
  - manual pick entry controls
  - in-draft rankings/suggestions refresh path
- **Extension**
  - draft-room detection
  - pick extraction + event emission
  - reconnect/backoff + `sync_state` handling
  - manual fallback affordance when selectors fail

This spec intentionally does **not** define exact files yet; that belongs in the plan after approval.

## Session and Event Model

### Draft session state must include

- `session_id`
- `user_id`
- `platform`
- `status`
- drafted picks / drafted players
- current turn or last processed pick
- sync-health state
- reconnect / resume token or equivalent resume identifier

### Required event types

- `pick`
- `sync_state`
- `get_suggestions`
- `suggestions`
- `state_update`
- `error`

### Pick event minimum fields

- player identifier
- pick number or draft position when available
- platform source
- timestamp
- ingestion mode (`auto` or `manual`)
- optional roster/team context when available

## Required Behavior

### Session lifecycle

- User can create a draft session from the web app.
- User can resume an active session after reconnect/reload.
- Session stores enough authoritative state to reconstruct draft progress.
- Session can be explicitly ended or expire safely after inactivity.

### Live pick sync

- Extension detects picks from supported draft-room selectors.
- Pick events are sent to the backend session stream.
- Backend validates, deduplicates, and persists accepted picks.
- Connected clients receive updated state.

### Rankings and suggestions refresh

- After each accepted pick, draft state updates.
- PuckLogic refreshes available-player context and recommendations.
- User sees updated rankings/suggestions without losing draft continuity.

### Manual fallback

- User can enter picks manually at any time.
- Manual entry is available when:
  - extension is unavailable
  - platform detection fails
  - sync becomes unreliable
- Manual entry writes to the same session-state model as automatic ingestion.

### Recovery and reconnect

- On reconnect, client or extension requests authoritative session state.
- Backend returns `sync_state` for reconciliation.
- Product surfaces sync health clearly enough for user trust decisions.

## UX States

The UI must clearly represent:

- connected
- reconnecting
- disconnected
- out of sync
- manual fallback active

The user must be able to:

- start live sync
- resume/reconnect a session
- switch to manual mode
- enter a missed pick manually
- inspect current sync health

## Acceptance Criteria

### Product acceptance

- [ ] A real user can start a live draft session and use it during a real draft.
- [ ] Picks are captured and reflected in session state in near real time.
- [ ] Rankings/suggestions update after accepted picks.
- [ ] Refresh/reconnect preserves usable draft continuity.
- [ ] User can continue via manual fallback if automatic sync fails.
- [ ] Sync health is visible in the UI.
- [ ] Live draft sync is treated as required launch scope in downstream planning.

### Backend / session acceptance

- [ ] Draft-session ownership and auth checks are enforced server-side.
- [ ] Reconnect restores authoritative session state well enough to continue drafting.
- [ ] Duplicate and missed pick handling are defined.
- [ ] Manual and automatic pick ingestion converge into one session model.

### Extension / platform acceptance

- [ ] ESPN live draft sync is launch-ready.
- [ ] Selector failures do not fully block draft use because manual fallback exists.
- [ ] Extension interruption does not permanently strand the session.

### Verification acceptance

- [ ] Automated tests cover draft-session lifecycle and pick-state reconciliation.
- [ ] Automated tests cover duplicate/missed pick handling.
- [ ] Automated tests cover manual pick ingestion.
- [ ] Automated tests cover reconnect or `sync_state` recovery semantics.
- [ ] Manual verification proves the end-to-end workflow is usable in a real draft-like session.

## Risks and Guardrails

- **DOM churn:** ESPN/Yahoo draft-room markup can change; implementation must use multiple selectors and degrade to manual fallback.
- **MV3 lifecycle:** service worker termination and reconnect timing must be treated as standard behavior.
- **Desync risk:** extension, UI, and backend can diverge unless server state stays authoritative.
- **Scope blow-up:** requiring ESPN and Yahoo equally at launch materially increases risk.
- **Auth/entitlement failures:** if the session cannot recover auth cleanly, the draft flow becomes launch-blocking.

## Resolved Questions

- Live draft sync is required for launch.
- Manual fallback is required for launch.
- Session recovery/reconnect is required for launch.
- Live draft sync requires authentication.
- ESPN is the minimum launch-critical platform.

## Open Questions

1. Is Yahoo also launch-required, or only best-effort at launch?
2. Is paid entitlement enforced at launch, or is authentication alone sufficient for the initial release?
3. How draft-aware must suggestions be at v1: simple best-available versus roster-aware recommendations?
4. What user-visible freshness threshold is acceptable for “near real time” during an actual draft?

## Recommendation

Approve this spec with the following guardrail:

> Launch requires reliable ESPN live draft sync, reconnectable draft sessions, and manual fallback. Yahoo may ship at launch only if it does not jeopardize ESPN stability or recovery quality.

Do not proceed to planning until this spec is approved.
