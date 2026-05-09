# Research: Milestone D — Web Draft Kit UI Codebase Survey

**Date:** 2026-05-05  
**Track:** research (pre-brainstorm)  
**Feeds:** Milestone D brainstorm → spec 010 design-system completion → plan 010a execution

---

## Objective

Survey the actual state of `apps/web` to understand what is implemented vs. scaffolded vs. missing — so brainstorming starts from reality, not from the reference docs (which have drifted).

---

## What Is Actually Implemented

### App Shell / Routes

| File | Status | Notes |
|---|---|---|
| `src/app/layout.tsx` | Bare scaffold | No Zustand provider, no auth wrappers, no font setup beyond metadata |
| `src/app/page.tsx` | "Coming soon" placeholder | Hard-coded Tailwind; no rankings data, no auth redirect |
| `src/app/dashboard/page.tsx` | **Working** | Client component; loads sources + rankings from API; uses `SourceWeightSelector` + `RankingsTable`; "Compute Rankings" button |
| `src/app/globals.css` | Bare | `@tailwind base/components/utilities` only — zero design tokens |

No auth routes (`login`, `signup`, `callback`), no middleware, no route protection of any kind.

### Components

| Component | Status |
|---|---|
| `SourceWeightSelector.tsx` | **Implemented** (called `SourceWeightSelector`, not `WeightControls` as the reference doc says) |
| `RankingsTable.tsx` | **Implemented** |
| `AppShell.tsx` | Missing |
| `KitSwitcher.tsx` | Missing |
| `PreDraftWorkspace.tsx` | Missing |
| `LiveDraftScreen.tsx` | Missing |

### Zustand Store

| Slice | Status |
|---|---|
| `store/slices/sources.ts` | **Implemented** — sources list, equal-weight distribution, `setSources`, `setWeight`, `resetWeights`, `activeWeights()` |
| `store/slices/rankings.ts` | **Implemented** — season, rankings, loading, error, cached, computedAt |
| `store/slices/kits.ts` | **Missing** — no kit management slice |
| `store/slices/draftSession.ts` | **Missing** — no live session state |
| `store/slices/auth.ts` | **Missing** — no auth state slice |

### API Clients (`src/lib/api/`)

| File | Status |
|---|---|
| `index.ts` | **Implemented** — `apiFetch()`, `ApiError` |
| `rankings.ts` | **Implemented** — `computeRankings()` |
| `sources.ts` | **Implemented** — `fetchSources()` |
| `scoring-configs.ts` | **Implemented** — `fetchScoringConfigPresets()` |
| `user-kits.ts` | **Exists** (not audited in detail) |
| `draft-sessions.ts` | **Missing** |
| `entitlements.ts` | **Missing** (needed from 011a `GET /entitlements`) |

### Design Tokens

`globals.css` is bare Tailwind. Zero CSS custom properties. The design system section of spec 010 is still marked **PENDING**. No token layer exists.

---

## Reference Doc Drift (Real vs. Documented)

| `frontend-reference.md` says | Reality |
|---|---|
| `src/components/WeightControls.tsx` | `SourceWeightSelector.tsx` |
| `src/store/rankings.ts` (flat file) | `src/store/slices/rankings.ts` (slice pattern) |
| `src/store/kits.ts` | Does not exist |
| `src/store/auth.ts` | Does not exist |
| `src/lib/supabase.ts` | `src/lib/supabase/client.ts` |
| `src/lib/supabase-server.ts` | `src/lib/supabase/server.ts` |
| `(auth)/` route group with login/signup/callback | Does not exist |
| `middleware.ts` with session refresh + route protection | Does not exist |

`apps/web/CLAUDE.md` also still shows Phase 2 store slices and components as `⬜ TODO`, but they're implemented. That file needs a pass before implementation begins.

---

## Key Gaps to Close in Milestone D

### Must-have for launch (from spec 009 + 010)

1. **App shell** — slim header (logo, pass balance, user menu) + kit context bar (active kit name, league dropdown, weights dropdown, compute action)
2. **Landing page** — default rankings for unauthenticated users with auth CTA banner; currently "Coming soon"
3. **Auth flow** — login/signup/callback pages + middleware route protection + Supabase session wiring
4. **Kit management** — kits store slice + `KitSwitcher` slide-in panel + kit CRUD (create, rename, duplicate, delete)
5. **Pre-draft workspace** — persistent right panel (weights + league profile + export); adapt current `dashboard/page.tsx`
6. **Live draft screen** — `LiveDraftScreen` component, draft session API client, `draftSession` store slice, sync/manual-mode states
7. **Design system token layer** — CSS custom properties in `globals.css` (colors, typography, spacing, radii, elevation); referenced from Tailwind config
8. **Entitlement surface** — pass balance in shell header, auth/pay gates on export + live draft entry (from 011a backend)

### Lower-priority / can scaffold

- Pick log drawer
- Manual pick entry drawer
- Reconnect banner (inline, not modal)
- Mobile responsive drawer behavior (can be progressive enhancement)

---

## Open Questions (Blocking Brainstorm)

1. **Route shape for live draft:** Should the live session be `/dashboard/live` (nested under auth-protected dashboard layout) or a separate top-level `/live` route? This affects the App Router layout tree and the auth middleware matcher.

2. **Pass balance data in shell:** Render live from `GET /entitlements` on every page load, or cache in Zustand on session start? Has latency implications for perceived shell responsiveness.

3. **Unauthenticated landing page scope:** Does the launch landing page need a distinct `/` route that shows default rankings without the kit context bar, or should unauthenticated users at `/` be redirected to `/dashboard` once auth is wired? Affects middleware logic and whether we need two shell variants.

4. **Auth provider pattern:** The Supabase auth clients exist but there's no React context/provider or auth Zustand slice. Does auth state live in Zustand (like the reference doc suggests) or purely in Supabase SSR cookies accessed server-side?

5. **Design system scope:** Spec 010 says "to be defined before Milestone D begins." Does the design system section need to be completed and merged into spec 010 before implementation starts, or can we close it as a Wave 5 task per plan 010a?

---

## Recommendation for Brainstorm

Start brainstorm with the five open questions above as explicit agenda items. The implementation wave order in plan 010a (landing + shell → workspace → session → live screen → design tokens) is sound, but the open questions need decisions before wave 1 and wave 3 can be coded without rework.

The frontend-reference.md and apps/web/CLAUDE.md should be updated as a mechanical track task before (or alongside) Milestone D implementation — the drift will confuse any spec/plan review.
