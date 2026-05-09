# PuckLogic Web — Claude Code Context

Next.js 14+ (App Router) frontend for the PuckLogic fantasy hockey draft kit.
Dev server: `http://localhost:3000`

---

## Quick Commands

```bash
# from apps/web/
pnpm dev             # dev server on :3000
pnpm test            # Vitest (single pass)
pnpm test:watch      # Vitest (watch mode)
pnpm test:coverage   # Vitest with v8 coverage
pnpm build           # production build
pnpm lint            # ESLint
```

---

## Directory Layout

```
apps/web/src/
  app/
    layout.tsx           # Root layout (fonts, globals.css)
    page.tsx             # Value prop landing page
    globals.css          # PL token layer + shadcn bridge + Tailwind base
    (auth)/
      layout.tsx         # Auth gate: getUser → redirect /login; entitlements fetch; AppShell
      dashboard/
        layout.tsx       # Kit context bar layout wrapper
        page.tsx         # Server Component: PreDraftWorkspace
      live/
        layout.tsx       # Live-mode layout: ReconnectBanner above children
        page.tsx         # Live draft route: LiveDraftScreen
    login/
      page.tsx           # Login form (outside auth group)
    signup/
      page.tsx           # Signup form (outside auth group)
    auth/
      callback/
        route.ts         # Supabase PKCE code exchange
  components/
    AppShell.tsx               # Shell header: logo, passBalance, UserMenuButton
    UserProvider.tsx           # 'use client'; onAuthStateChange; useUser() hook
    KitSwitcher.tsx            # Right slide-in: kit list, active indicator, CRUD
    PreDraftWorkspace.tsx      # Rankings table + right panel (weights, exports)
    StartDraftModal.tsx        # 'use client'; createSession → cookie → store → /live
    LiveDraftScreen.tsx        # Full live draft layout
    ManualPickDrawer.tsx       # Slide-in: player search, row select, confirm
    ReconnectBanner.tsx        # Reconnecting/disconnected inline banner
    SourceWeightSelector.tsx   # ✅ Complete — sliders per source, equalise button
    RankingsTable.tsx          # ✅ Complete — sortable table, per-source rank columns
    __tests__/
  lib/
    api/
      index.ts           # ✅ Complete — apiFetch() wrapper; ALL backend calls go here
      entitlements.ts    # GET /entitlements client
      draft-sessions.ts  # POST /start, /{id}/resume, /{id}/manual-picks, /{id}/end; GET /{id}/sync-state
      user-kits.ts       # listKits, createKit, updateKit, deleteKit, duplicateKit
      __tests__/
    supabase/
      client.ts          # ✅ Complete — Supabase browser client (auth only)
      server.ts          # ✅ Complete — Supabase server client (auth only)
  middleware.ts          # Session refresh, route protection, / → /dashboard redirect
  store/
    index.ts             # ✅ Complete — Zustand slice composition
    slices/
      sources.ts         # ✅ Complete — sources + weights slice
      rankings.ts        # ✅ Complete — computed rankings slice
      kits.ts            # Active kit selection; kit CRUD
      draftSession.ts    # Live session state: picks, mode, status
    __tests__/
  types/
    index.ts             # ✅ Complete — Source, RankedPlayer, RankingsResult, UserKit, DraftPick
  test/
    setup.ts             # jest-dom matchers imported globally
    vitest.d.ts          # Vitest type augmentation
```

---

## Version Scope

| Version | Trends UI |
|---------|-----------|
| **v1.0** | Pre-season breakout/regression badges (`breakout_score`, `regression_risk`) displayed inline on the `RankingsTable`. No separate Trends tab. |
| **v2.0** | Full Trends tab on the dashboard with 14-day in-season signal cards, Z-score explanations, and the paywall gate (free users see all except top 10). Also surfaced in the Chrome extension Trends panel. |

Do not build v2.0 Trends UI components until the in-season engine (Layer 2) is scoped for implementation.

---

## Milestone Status

| Area | Status | Notes |
|------|--------|-------|
| `lib/api/index.ts` | ✅ Complete | `apiFetch()`, `ApiError` |
| `lib/supabase/` | ✅ Complete | Auth-only; do not use for data fetching |
| `types/index.ts` | ✅ Complete | `Source`, `RankedPlayer`, `RankingsResult`, `UserKit`, `DraftPick` |
| `store/index.ts` | ✅ Complete | Slice composition |
| `store/slices/sources.ts` | ✅ Complete | `sources`, `weights`, `setWeight`, `resetWeights`, `fetchSources` |
| `store/slices/rankings.ts` | ✅ Complete | `rankings`, `isLoading`, `error`, `computeRankings` |
| `store/slices/kits.ts` | ✅ Complete | Active kit selection; kit CRUD |
| `store/slices/draftSession.ts` | ✅ Complete | Live session state: picks, mode, status |
| `components/SourceWeightSelector.tsx` | ✅ Complete | Slider per source, equalise button |
| `components/RankingsTable.tsx` | ✅ Complete | Sortable table, per-source rank columns |
| `components/AppShell.tsx` | ✅ Complete | Shell header: logo, passBalance, UserMenuButton |
| `components/UserProvider.tsx` | ✅ Complete | `'use client'`; `useUser()` hook |
| `components/KitSwitcher.tsx` | ✅ Complete | Right slide-in; kit CRUD |
| `components/PreDraftWorkspace.tsx` | ✅ Complete | Rankings table + right panel |
| `components/StartDraftModal.tsx` | ✅ Complete | Session creation → cookie → store → /live |
| `components/LiveDraftScreen.tsx` | ✅ Complete | Full live draft layout |
| `components/ManualPickDrawer.tsx` | ✅ Complete | Player search, row select, confirm pick |
| `components/ReconnectBanner.tsx` | ✅ Complete | Reconnecting/disconnected banner |
| `app/(auth)/dashboard/page.tsx` | ✅ Complete | Server Component: PreDraftWorkspace |
| `app/(auth)/live/page.tsx` | ✅ Complete | Server Component: LiveDraftScreen |
| `middleware.ts` | ✅ Complete | Route protection with PUBLIC_PATHS exclusion |
| `lib/api/entitlements.ts` | ✅ Complete | GET /entitlements |
| `lib/api/draft-sessions.ts` | ✅ Complete | Full session lifecycle API |
| `lib/api/user-kits.ts` | ✅ Complete | listKits, createKit, updateKit, deleteKit, duplicateKit |

---

## API Client Rules

**All backend calls must go through `lib/api/index.ts`.** Never call Supabase for data — it is auth-only.

```typescript
// lib/api/index.ts — add Phase 2 methods here
export async function getSources(token: string): Promise<Source[]> {
  return apiFetch<Source[]>("/sources", { token });
}

export async function computeRankings(
  req: { season: string; weights: Record<string, number> },
  token: string,
): Promise<RankingsResult> {
  return apiFetch<RankingsResult>("/rankings/compute", {
    method: "POST",
    body: JSON.stringify(req),
    token,
  });
}
```

---

## Zustand Store Pattern

Slices are created with the `StateCreator` pattern and composed in `store/index.ts`.

```typescript
// store/slices/sources.ts
import { StateCreator } from "zustand";

export interface SourcesSlice {
  sources: Source[];
  weights: Record<string, number>;
  setWeight: (sourceName: string, value: number) => void;
  resetWeights: () => void;
  fetchSources: (token: string) => Promise<void>;
}

export const createSourcesSlice: StateCreator<SourcesSlice> = (set) => ({
  sources: [],
  weights: {},
  setWeight: (name, value) =>
    set((s) => ({ weights: { ...s.weights, [name]: value } })),
  resetWeights: () => set({ weights: {} }),
  fetchSources: async (token) => { /* call getSources() */ },
});

// store/index.ts
export const useStore = create<SourcesSlice & RankingsSlice>()((...a) => ({
  ...createSourcesSlice(...a),
  ...createRankingsSlice(...a),
}));
```

---

## Shared Types (`src/types/index.ts`)

Phase 2 types to define (mirror the backend Pydantic schemas):

```typescript
export interface Source {
  id: string;
  name: string;
  display_name: string;
  url: string | null;
  active: boolean;
}

export interface RankedPlayer {
  composite_rank: number;
  composite_score: number;
  player_id: string;
  name: string;
  team: string | null;
  position: string | null;
  source_ranks: Record<string, number>;
}

export interface RankingsResult {
  season: string;
  computed_at: string;
  cached: boolean;
  rankings: RankedPlayer[];
}

export interface UserKit {
  id: string;
  name: string;
  season: string;
  weights: Record<string, number>;
  created_at: string;
}
```

---

## Environment Variables (`.env.local`)

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Never commit `.env.local`. It is gitignored.

---

## TDD Rules

1. **Write the test first.** Every component and hook ships with a test.
2. Use Vitest + React Testing Library. Config: `vitest.config.ts` (jsdom, globals).
3. Mocks over real I/O — `vi.spyOn(apiModule, 'getSources')` etc.; never hit the real API.
4. Co-locate tests in `__tests__/` next to the source file.
5. All tests must be green (`pnpm test`) before committing.

### Component test pattern

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SourceWeightSelector } from "../SourceWeightSelector";

it("calls setWeight when slider is moved", async () => {
  const setWeight = vi.fn();
  render(<SourceWeightSelector sources={mockSources} weights={{}} setWeight={setWeight} />);
  // ...
});
```

---

## Coding Conventions

- All components are React Server Components by default; add `"use client"` only when needed (event handlers, hooks, browser APIs).
- Styling: Tailwind CSS utility classes + `shadcn/ui` components.
  - Add shadcn components: `npx shadcn@latest add <name>` from `apps/web/`.
- State: Zustand for global client state; SWR or React Query for server data where appropriate.
- No `any` — use proper TypeScript types from `src/types/index.ts`.
- Imports: use `@/` path alias (maps to `src/`).

## MCP Tools

Always use Context7 MCP when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask.
