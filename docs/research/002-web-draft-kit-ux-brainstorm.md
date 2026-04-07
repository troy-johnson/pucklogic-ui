# 2026-04-06 — Web-First Draft Kit UX Brainstorm

**Status:** Brainstorm complete  
**Basis:** `docs/specs/009-web-draft-kit-ux.md`  
**Related:** `docs/specs/008-live-draft-sync-launch-required.md`, `docs/plans/008a-draft-season-readiness.md`

## Purpose

This brainstorm captures the approved planning direction to refine `009-web-draft-kit-ux.md` into a tighter implementation-ready spec. It focuses on the web-first draft kit experience, not deep extension UX.

## Context loaded

- Web is the primary launch surface
- Auth + saved kits are launch-required
- Live draft sync is launch-required
- Manual pick entry is a launch-required fallback
- Backend draft session state is authoritative
- Anonymous kits are already supported in canonical docs via `pucklogic_session`
- Anonymous kits already have a documented 7-day cleanup rule
- Export already requires auth in canonical backend docs

## Clarified product decisions from brainstorm

1. **Anonymous exploration policy**
   - Anonymous users can create a temporary kit and view rankings
   - Auth is required for durable saved kits, export/print, and starting a live draft

2. **League profile timing**
   - League profile is progressive, not required before first rankings view
   - It becomes required before meaningful saved prep and before live draft

3. **Live draft recommendation surface**
   - Launch uses one primary recommendation list
   - Deeper explanation is available in an expandable rationale panel/drawer

4. **Reconnect/resume behavior**
   - Guided recovery comes first
   - Manual fallback is the visible next step if reconciliation fails
   - This resumable flow assumes the user is authenticated

5. **Concurrent live sessions**
   - Launch allows one active live session per user

6. **Temporary anonymous kit retention**
   - Anonymous kits are directly resumable for 24 hours based on last activity
   - After 24 hours and before 7 days, recovery requires normal sign-in
   - After sign-in, temporary kits auto-migrate to the user account
   - After sign-in-based recovery, the user sees a confirmation banner/toast

7. **Temporary vs saved messaging**
   - Use both persistent lightweight temporary-state signaling and stronger contextual auth gates
   - Copy must explain that login is required to save kits, view previous saved kits, export, and start live draft

8. **Export placement**
   - Export/print belongs inside the pre-draft workspace
   - Export is gated by auth and valid prep completion

9. **Export readiness rule**
   - Export unlocks when the user is authenticated, an active kit is selected, the league profile is complete enough for rankings, and rankings are in a valid computed state
   - “Valid computed state” means the latest ranking request completed without error, produced a non-empty result, matches the current kit + league profile context, and is not stale/loading/error

10. **Rationale coverage direction**
    - Launch should guarantee deeper rationale for the decision-relevant player cohort
    - If implementation cost is negligible, rationale may be available for all players
    - The exact threshold rule still needs spec-phase refinement

## Approaches considered

### Approach 1 — Strict account-first planner

**Shape**
- Anonymous users can browse only
- Auth required for kits, rankings, export, and live draft
- League profile required early

**Pros**
- Cleanest state model
- Lowest lifecycle ambiguity
- Simplest support model

**Cons**
- High onboarding friction
- Weak exploration/conversion balance
- Not aligned with approved anonymous exploration direction

### Approach 2 — Progressive anonymous exploration with recovery gates

**Shape**
- Anonymous users can explore rankings and create a temporary kit
- Auth required for durable save, export, and live draft
- League profile is progressive
- Temporary kits are easy-return for 24 hours, then login-gated through day 7
- Mid-flow auth migrates the temporary kit to the account
- Live draft supports one active session per user
- Drafting centers on one primary recommendation list with expandable rationale
- Recovery prefers retry/resume first, then manual fallback

**Pros**
- Best balance of usability, conversion, and launch scope
- Preserves meaningful exploration without weakening durable account value
- Matches current architecture decisions already documented
- Keeps extension integration secondary to web UX

**Cons**
- More state combinations to represent clearly
- Requires strong temporary-versus-saved messaging
- Needs a reclaim flow after the easy-return window

### Approach 3 — Power-user draft console

**Shape**
- Richer dense draft console from day one
- More comparison surfaces and advanced detail in the live draft UI

**Pros**
- Potentially stronger differentiation for expert users
- More visible decision support depth

**Cons**
- Highest design and implementation complexity
- Greater launch risk
- Misaligned with the approved one-primary-list recommendation model

## Recommended direction

**Recommend: Approach 2 — Progressive anonymous exploration with recovery gates**

### Why

- It matches the approved product choices from the brainstorm
- It preserves the existing 7-day anonymous retention architecture while adding a stronger conversion-oriented reclaim model
- It keeps the launch UX web-first and understandable
- It protects live draft resiliency with manual fallback without centering the extension
- It provides a clean handoff into spec refinement and later ADR capture

## Recommended rules to carry into the spec

1. Anonymous exploration is allowed, but durable value requires auth
2. Temporary anonymous kits are easy-return for 24 hours based on last activity
3. Temporary kits remain recoverable via normal sign-in until day 7
4. Mid-flow auth migrates temporary kit ownership to the user account
5. League profile is progressive but required before high-stakes actions
6. Export remains inside prep and is gated by auth + valid prep state
7. Live draft allows one active session per user at launch
8. Live draft uses one primary recommendation list with expandable rationale
9. Deeper rationale is guaranteed for the decision-relevant cohort; broader coverage is allowed if cheap
10. Reconnect/resume uses guided recovery first, then manual fallback
11. Anonymous state must be visibly temporary through persistent status plus contextual auth gates

## Assumptions

- Anonymous users will tolerate auth gates if they have already received meaningful exploratory value
- Users will understand the difference between temporary browser-scoped work and account-saved work if the copy is explicit
- A single active live session per user is sufficient for launch
- Normal sign-in is enough for reclaiming older temporary work; a separate restore surface is not required at launch

## Open questions for spec refinement

1. How exactly should the decision-relevant rationale cohort be defined?
   - Candidate models: fixed rank cutoff, expected drafted-player count, VORP threshold, or hybrid rule
   - This should be resolved in the spec phase before implementation and before high-fidelity wireframes are treated as final

2. What exact fields make a league profile “complete enough” for export/readiness gating?

3. What exact copy should appear for:
   - temporary kit status
   - auth gate at save/export/live draft
   - reclaimed temporary kit after sign-in

4. Should account creation and sign-in share one recovery-friendly auth surface or remain distinct flows in the wireframes?

## ADR signal detected

These decisions have architecture-level impact and should be captured in an ADR:

- Web is the primary launch surface for draft prep and live session control
- Backend draft session state is authoritative
- One active live session per user at launch
- Temporary anonymous kits use a two-window lifecycle: 24-hour easy return, 7-day login-gated recovery
- Mid-flow auth migrates temporary kit ownership to the user account
- Live draft recovery and manual fallback depend on authenticated session ownership

## Self-review

- No placeholders remain
- Alternatives are documented
- Recommendation is explicit
- Assumptions and open questions are listed
- Scope remains centered on the web product

## Recommendation

Use this brainstorm as the approved basis for refining `009-web-draft-kit-ux.md` and for drafting a supporting ADR covering session ownership, temporary-kit lifecycle, and launch auth boundaries.
