# Plan: Web Draft Kit UI and Live Session Screens

**Spec basis:** `docs/specs/009-web-draft-kit-ux.md`, `docs/specs/010-web-ui-wireframes-design.md`  
**Branch:** `feat/live-draft-sync-backend-contract`  
**Risk Tier:** 2 — Cross-route UI, state management, app shell  
**Scope:** Large (~3–5 days, multi-session)  
**Execution mode:** Dependency waves

**Execution status (2026-04-11):** Deferred behind `008b` and `008c` except for limited shell/data-boundary scaffolding.
**Readiness:** Scaffold-only until spec `010` is approved and design-system decisions are closed; avoid full layout/polish implementation before that gate passes.

---

## Goal

Build the web-first draft kit experience defined by specs 009 and 010: landing/default rankings, app shell, kit context bar, pre-draft workspace, live draft screen, and visible sync/manual fallback states.

## Non-Goals

- Browser-extension DOM parsing
- Final marketing landing page beyond the launch default-rankings experience
- Multi-user collaboration
- Deep export polish beyond what current backend routes already support

---

## File Surface

| File | Change |
|---|---|
| `apps/web/src/app/page.tsx` | Replace placeholder home with default-rankings launch landing page |
| `apps/web/src/app/layout.tsx` | Add app-shell wrappers and metadata alignment |
| `apps/web/src/app/globals.css` | Add design tokens, color modes, spacing, and shared surface primitives |
| `apps/web/src/app/dashboard/page.tsx` | Evolve current rankings page into the pre-draft workspace |
| `apps/web/src/store/index.ts` | Add draft-session slice wiring |
| `apps/web/src/store/slices/draftSession.ts` | Create live-session state slice |
| `apps/web/src/store/__tests__/draftSession.test.ts` | Add live-session store tests |
| `apps/web/src/lib/api/draft-sessions.ts` | Create draft-session API client |
| `apps/web/src/lib/api/__tests__/draft-sessions.test.ts` | Add API client tests |
| `apps/web/src/components/AppShell.tsx` | Create shared shell and kit context bar |
| `apps/web/src/components/KitSwitcher.tsx` | Create right-side kit switcher |
| `apps/web/src/components/PreDraftWorkspace.tsx` | Create rankings + right panel workspace wrapper |
| `apps/web/src/components/LiveDraftScreen.tsx` | Create live draft session layout |
| `apps/web/src/components/__tests__/AppShell.test.tsx` | Add shell tests |
| `apps/web/src/components/__tests__/KitSwitcher.test.tsx` | Add switcher tests |
| `apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx` | Add workspace tests |
| `apps/web/src/components/__tests__/LiveDraftScreen.test.tsx` | Add live screen tests |

---

## Implementation Phases

### Phase 1 — Launch entry and shell

Replace the current “Coming soon” and basic dashboard framing with the launch shell: header, pass-balance slot, kit context bar, and default-rankings landing path.

### Phase 2 — Pre-draft workspace

Adapt the existing rankings flow into the canonical prep workspace with persistent right panel behavior, weight controls, and kit context visibility.

### Phase 3 — Live draft state integration

Add session API wiring and client state management so the web app can start/resume a session and render sync/manual-mode state from authoritative backend data.

### Phase 4 — Live draft layout

Implement the wireframed live screen: available players, suggestion stack, roster-needs block, team list, and sync-status bar.

### Phase 5 — Design-system closure

Define the minimum token layer required by spec 010 so implementation planning no longer depends on unfinished design-system work.

---

## Task List

### Wave 1 — landing and shell

1. **Add failing tests for the launch landing page showing default rankings context.**  
   Command: `pnpm --filter @pucklogic/web test -- src/app/dashboard/__tests__/page.test.tsx`  
   Expected: tests fail because the current home page is still a placeholder.

2. **Replace `apps/web/src/app/page.tsx` with the default-rankings launch landing page.**  
   Command: `pnpm --filter @pucklogic/web test -- src/app/dashboard/__tests__/page.test.tsx`  
   Expected: landing tests pass.

3. **Add failing shell tests for header, pass slot, and kit context bar.**  
   Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/AppShell.test.tsx`  
   Expected: tests fail because the shared shell does not exist.

4. **Implement `apps/web/src/components/AppShell.tsx` and wire it from `src/app/layout.tsx`.**  
   Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/AppShell.test.tsx`  
   Expected: shell tests pass.

### Wave 2 — pre-draft workspace

5. **Add failing tests for pre-draft workspace layout and right-panel behavior.**  
   Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/PreDraftWorkspace.test.tsx`  
   Expected: tests fail because the workspace wrapper does not exist.

6. **Implement `apps/web/src/components/PreDraftWorkspace.tsx` and refactor `src/app/dashboard/page.tsx` to use it.**  
   Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/PreDraftWorkspace.test.tsx`  
   Expected: pre-draft workspace tests pass.

7. **Add failing kit-switcher tests for select/create/rename/delete affordances.**  
   Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/KitSwitcher.test.tsx`  
   Expected: tests fail because the switcher panel does not exist.

8. **Implement `apps/web/src/components/KitSwitcher.tsx` and connect active-kit state.**  
   Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/KitSwitcher.test.tsx`  
   Expected: switcher tests pass.

### Wave 3 — session API and client state

9. **Add failing API client tests for create/resume/manual-pick draft-session calls.**  
   Command: `pnpm --filter @pucklogic/web test -- src/lib/api/__tests__/draft-sessions.test.ts`  
   Expected: tests fail because the draft-session client does not exist.

10. **Implement `apps/web/src/lib/api/draft-sessions.ts`.**  
    Command: `pnpm --filter @pucklogic/web test -- src/lib/api/__tests__/draft-sessions.test.ts`  
    Expected: API client tests pass.

11. **Add failing store tests for live-session state and sync/manual mode transitions.**  
    Command: `pnpm --filter @pucklogic/web test -- src/store/__tests__/draftSession.test.ts`  
    Expected: tests fail because the draft-session slice does not exist.

12. **Implement `apps/web/src/store/slices/draftSession.ts` and wire it in `src/store/index.ts`.**  
    Command: `pnpm --filter @pucklogic/web test -- src/store/__tests__/draftSession.test.ts`  
    Expected: store tests pass.

### Wave 4 — live draft screen

13. **Add failing live-screen tests for suggestions, roster needs, team list, and sync status.**  
    Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/LiveDraftScreen.test.tsx`  
    Expected: tests fail because the live screen does not exist.

14. **Implement `apps/web/src/components/LiveDraftScreen.tsx`.**  
    Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/LiveDraftScreen.test.tsx`  
    Expected: live-screen tests pass.

15. **Add live route wiring for session start/resume rendering.**  
    Command: `pnpm --filter @pucklogic/web test -- src/components/__tests__/LiveDraftScreen.test.tsx src/store/__tests__/draftSession.test.ts`  
    Expected: route-level live session wiring is covered by passing tests.

### Wave 5 — design-system baseline and verification

16. **Implement color, spacing, type, radius, and elevation tokens in `apps/web/src/app/globals.css`.**  
    Command: `pnpm --filter @pucklogic/web build`  
    Expected: the app builds successfully using the new token layer.

17. **Run the focused web verification suite.**  
    Command: `pnpm --filter @pucklogic/web test && pnpm --filter @pucklogic/web build`  
    Expected: all web tests pass and the production build succeeds.

---

## Verification Mapping

| Acceptance need | Covered by |
|---|---|
| Default rankings entry path | Tasks 1–2 |
| App shell + visible active kit context | Tasks 3–4 |
| Pre-draft workspace contract | Tasks 5–8 |
| Live draft start/resume client path | Tasks 9–12, 15 |
| Sync-health and manual-mode visibility | Tasks 11–15 |
| Wireframe and design-system closure | Tasks 13–17 |

---

## Risks

- **State-shape drift:** UI work depends on backend session payloads staying stable.
- **Design-system reversibility:** token names are easy to change now but expensive after component adoption.
- **Route churn:** current app has only a placeholder home and a basic dashboard, so shell decisions will reshape the route tree.

## Open Questions

1. Should the initial live route be nested under `/dashboard` or promoted to a top-level `/live` path?
2. Does launch require real pass-balance data in the shell immediately, or is a backend-connected placeholder acceptable during early implementation?
3. Should unauthenticated users be allowed to preview the live draft screen shell before the auth/pay gate, or only the prep experience?
