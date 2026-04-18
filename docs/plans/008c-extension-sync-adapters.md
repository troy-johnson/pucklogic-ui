# Plan: Extension Sync Adapters for ESPN MVP and Yahoo Secondary Support

**Spec basis:** `docs/specs/008-live-draft-sync-launch-required.md`, `docs/specs/009-web-draft-kit-ux.md`  
**Branch:** `feat/008c-extension-sync-adapters`  
**Risk Tier:** 3 — New package, browser runtime, DOM volatility  
**Scope:** Large (~3–5 days, multi-session)  
**Execution mode:** Dependency waves  
**Acceptance tier:** ESPN required, Yahoo stretch acceptance before launch

**Execution status (2026-04-14):** Active execution track after `008b` backend contract completion.
**Readiness:** Backend session/protocol dependency is satisfied on the current branch; ESPN MVP remains the next implementation focus and Yahoo is still non-blocking/stretch. Before implementation begins, refresh `docs/extension-reference.md` so adapter work follows the current transport/session contract instead of stale route and message-shape guidance.

## Infrastructure Assumptions

- Backend launches on **Fly.io** as a **single FastAPI instance**
- Extension uses **WebSocket** as the primary live-sync transport
- If the socket is unavailable, the product degrades to **manual fallback / HTTP-backed recovery** rather than blocking draft use
- Redis is **not** required for launch-time extension sync behavior
- Session inactivity expiry is a **backend-owned configurable policy**; the extension must not assume a fixed timeout duration

---

## Goal

Bootstrap the browser extension package and implement the sync adapter layer needed to connect supported draft rooms to the authoritative backend session. ESPN is the required MVP. Yahoo uses the same protocol and is pursued as a secondary launch target without blocking ESPN readiness.

The extension package should use a minimal Vite-based setup compatible with MV3 and the monorepo.

## Non-Goals

- Web app UI implementation
- Backend authority rules
- Perfect DOM durability without manual fallback
- Cross-browser marketplace submission work
- Advanced live suggestion sophistication beyond keeping accepted picks available to downstream recommendation logic

---

## File Surface

| File | Change |
|---|---|
| `packages/extension/package.json` | Create workspace package and scripts |
| `packages/extension/manifest.json` | Create extension manifest and permissions |
| `packages/extension/src/shared/protocol.ts` | Create message/event protocol shared across adapters |
| `packages/extension/src/background/index.ts` | Create background/session bridge |
| `packages/extension/src/content/espn.ts` | Create ESPN draft-room adapter |
| `packages/extension/src/content/yahoo.ts` | Create Yahoo draft-room adapter |
| `packages/extension/src/content/manualFallback.ts` | Create selector-failure escalation helper |
| `packages/extension/src/__tests__/protocol.test.ts` | Add protocol tests |
| `packages/extension/src/__tests__/background.test.ts` | Add reconnect and forwarding tests |
| `packages/extension/src/__tests__/espn.test.ts` | Add ESPN adapter tests |
| `packages/extension/src/__tests__/yahoo.test.ts` | Add Yahoo adapter tests |
| `packages/extension/src/__tests__/fallback.test.ts` | Add manual fallback tests |

---

## Implementation Phases

### Phase 1 — Package bootstrap

Create the extension workspace package and minimal runtime/build/test wiring so later adapter work lands in a stable package boundary.

### Phase 2 — Shared protocol and background bridge

Define the exact event shapes used to forward picks, receive `sync_state`, and communicate reconnect/manual-mode transitions.

### Phase 3 — ESPN adapter

Implement the launch-critical adapter with multiple selectors and resilient pick extraction.

### Phase 4 — Yahoo adapter

Implement the same protocol against Yahoo draft-room structure as a secondary acceptance target.

Yahoo should remain gated and non-blocking until manual draft-room verification succeeds, even if automated adapter tests pass.

### Phase 5 — Manual fallback behavior

When selectors fail or sync confidence drops, surface manual fallback immediately rather than silently failing.

---

## Task List

### Wave 1 — bootstrap and protocol

1. **Create the `packages/extension` workspace package and install dependencies.**  
   Command: `pnpm install`  
   Expected: the new workspace package resolves successfully.

2. **Add failing protocol tests for extension ↔ backend session messages.**  
   Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/protocol.test.ts`  
   Expected: tests fail because the protocol module does not exist yet.

3. **Implement `packages/extension/src/shared/protocol.ts`.**  
   Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/protocol.test.ts`  
   Expected: protocol tests pass.

4. **Add failing background tests for reconnect and event forwarding.**  
   Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/background.test.ts`  
   Expected: tests fail because the background bridge does not exist.

5. **Implement the background session bridge.**  
   Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/background.test.ts`  
   Expected: background tests pass.

### Wave 2 — ESPN MVP

6. **Add failing ESPN adapter tests for draft-room detection and pick extraction.**  
   Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/espn.test.ts`  
   Expected: tests fail because the ESPN adapter does not exist.

7. **Implement `packages/extension/src/content/espn.ts`.**  
   Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/espn.test.ts`  
   Expected: ESPN tests pass.

8. **Add failing ESPN reconnect/degraded-state tests that verify protocol-level recovery signals.**  
   Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/espn.test.ts -t reconnect`  
   Expected: reconnect tests fail until recovery behavior is implemented.  

9. **Implement ESPN degraded-state and reconnect signaling.**  
   Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/espn.test.ts -t reconnect`  
   Expected: reconnect tests pass.

### Wave 3 — Yahoo secondary support

10. **Add failing Yahoo adapter tests for detection and pick extraction.**  
    Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/yahoo.test.ts`  
    Expected: tests fail because the Yahoo adapter does not exist.

11. **Implement `packages/extension/src/content/yahoo.ts`.**  
    Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/yahoo.test.ts`  
    Expected: Yahoo tests pass.

### Wave 4 — fallback and verification

12. **Add failing tests for selector-failure escalation into manual fallback.**  
    Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/fallback.test.ts`  
    Expected: tests fail because fallback escalation does not exist.

13. **Implement manual fallback escalation helper.**  
    Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/fallback.test.ts`  
    Expected: fallback tests pass.

14. **Run the focused extension verification suite.**  
    Command: `pnpm --filter @pucklogic/extension test`  
    Expected: all extension tests pass.

---

### Wave 5 — pre-launch adapter observability

15. **Add failing tests for adapter observability metrics around attach success/failure, reconnect recovery, and manual fallback activation.**  
    Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/protocol.test.ts src/__tests__/background.test.ts -t observability`  
    Expected: tests fail until adapter metrics hooks are added.

16. **Implement pre-launch adapter metrics for attach success/failure, reconnect recovery, selector fallback, and manual fallback activation.**  
    Command: `pnpm --filter @pucklogic/extension test -- src/__tests__/protocol.test.ts src/__tests__/background.test.ts -t observability`  
    Expected: observability tests pass and adapter metrics are ready for launch signoff.

## Required dependency / backend follow-up

- Confirm and document the backend-owned configurable inactivity-timeout behavior used for abandoned draft sessions.
- If backend behavior is not fully implemented yet, track it as a required backend follow-up while keeping the extension implementation timeout-agnostic.
- Treat advanced live suggestion behavior as a separate pre-launch requirement rather than a transport-blocking `008c` deliverable.

## Verification Mapping

| Acceptance need | Covered by |
|---|---|
| ESPN launch-critical sync | Tasks 6–9 |
| Yahoo secondary support | Tasks 10–11 |
| Reconnect and recovery signals | Tasks 4–5, 8–9 |
| Manual fallback when selectors fail | Tasks 12–13 |

---

## Risks

- **No existing package:** extension bootstrap is a structural change to the monorepo.
- **DOM churn:** selectors for both ESPN and Yahoo will drift; fallback must be considered normal, not exceptional.
- **Permission surface:** host permissions and background/runtime setup are security-sensitive and somewhat hard to undo once shipped.
- **Single-instance assumption:** reconnect logic must resync from backend authority and never assume cross-instance state fanout exists at launch.

## Open Questions

Resolved decisions:

1. Use a minimal **Vite** setup for `packages/extension`.
2. Keep Yahoo **gated / non-blocking** until manual draft-room verification succeeds.
3. Use a **hybrid status model**: the extension may expose a minimal local sync-health indicator, while richer user-visible sync/workflow status remains in the web app.
4. Treat session inactivity expiry as a **backend-owned configurable timeout**; track any backend implementation/documentation gap as both an `008c` dependency and a backend follow-up item.
5. Defer advanced live suggestion behavior to a separate pre-launch requirement.
