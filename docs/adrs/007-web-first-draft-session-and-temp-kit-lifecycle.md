# ADR 007 — Web-First Draft Session and Temporary Kit Lifecycle

**Status:** Draft  
**Date:** 2026-04-06  
**Related:** `docs/specs/009-web-draft-kit-ux.md`, `docs/research/009-web-draft-kit-ux-brainstorm.md`, `docs/specs/008-live-draft-sync-launch-required.md`

## Context

The product needs a stable launch architecture for web-first draft prep and live draft operation. Current canonical docs already establish backend-authoritative draft sessions, anonymous session-token kit support, 7-day anonymous kit cleanup, and auth-gated export/live capabilities. What remained unclear was how these choices should combine into a coherent web-first lifecycle for temporary work, authentication transitions, and resumable live sessions.

## Decision

1. **Web is the primary launch surface** for draft prep, saved kits, rankings, export, and live draft session control.
2. **Backend draft session state is authoritative** for live draft and recovery flows.
3. **Anonymous users may explore** by creating temporary kits and viewing rankings.
4. **Authentication is required** for durable saved kits, export/print, and starting a live draft.
5. **Temporary anonymous kits follow a two-window lifecycle**:
   - directly resumable for 24 hours based on last activity
   - recoverable by normal sign-in through day 7
6. **Temporary kits auto-migrate to `user_id` on authentication**.
7. **Launch supports one active live draft session per user**.
8. **Reconnect/resume and guided recovery are authenticated session behaviors**; manual fallback remains first-class if reconciliation fails.

## Consequences

### Positive

- Preserves low-friction exploration while protecting durable value behind auth
- Reuses already-documented anonymous-kit architecture rather than replacing it
- Keeps launch UX centered on the web product instead of extension-led workflows
- Simplifies live session ownership and recovery semantics

### Negative

- Introduces a more nuanced temporary-versus-saved lifecycle that UI copy must explain clearly
- Requires reclaim behavior after the 24-hour direct-return window
- Defers multi-session power-user workflows until after launch

## Alternatives considered

### 1. Auth-required early for most meaningful actions

**Rejected** because it reduces exploration value and conflicts with the approved web-first discovery model.

### 2. Fully durable anonymous prep without meaningful auth gates

**Rejected** because it weakens account value, complicates ownership semantics, and conflicts with existing auth-gated export/live behavior.

### 3. Multiple concurrent live sessions at launch

**Rejected** because it increases session management complexity and support ambiguity without being necessary for launch.

## Follow-up decisions still required

- Define the exact “decision-relevant player cohort” rule for deeper rationale coverage
- Define the exact league-profile completeness requirements for export/readiness gating
- Define the final user-facing copy for temporary status, auth gates, and reclaimed work

## Resulting guidance

- The web app should visually distinguish temporary anonymous work from account-saved work
- Auth transition flows should preserve user progress by migrating temporary kits automatically
- Live draft wireframes and implementation should assume one active session per user and authoritative backend reconciliation
