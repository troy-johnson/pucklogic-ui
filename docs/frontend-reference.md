# PuckLogic — Frontend Reference

**Domain:** Next.js web app (`apps/web/`) + shared UI package (`packages/ui/`)
**See also:** [pucklogic-architecture.md](pucklogic-architecture.md) for system overview

---

## 1. Project Structure

```
apps/web/
├── src/
│   ├── app/                          # App Router
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx        # Supabase Auth UI — sign in
│   │   │   ├── signup/page.tsx       # Supabase Auth UI — sign up
│   │   │   └── callback/route.ts     # OAuth code → session exchange
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx            # Protected layout (redirect if no session)
│   │   │   ├── dashboard/page.tsx    # Rankings dashboard (core product)
│   │   │   ├── trends/page.tsx       # ML Trends tab
│   │   │   └── settings/page.tsx     # Kit & scoring config
│   │   ├── layout.tsx                # Root layout — fonts, global providers
│   │   └── page.tsx                  # Landing page → /dashboard if authed
│   ├── components/
│   │   ├── WeightControls.tsx        # Source weight sliders
│   │   ├── RankingsTable.tsx         # Sortable/filterable rankings grid
│   │   ├── PlayerCard.tsx            # Player detail popover
│   │   ├── ExportPanel.tsx           # PDF/Excel download buttons
│   │   ├── ScoringConfigPanel.tsx    # Fantasy scoring preset + custom editor
│   │   └── TrendsPanel.tsx           # Breakout/regression scores + SHAP explainer
│   ├── lib/
│   │   ├── supabase.ts               # Browser Supabase client
│   │   ├── supabase-server.ts        # Server Supabase client factory
│   │   └── api/
│   │       ├── rankings.ts           # computeRankings() — POST /rankings/compute
│   │       ├── sources.ts            # fetchSources() — GET /sources
│   │       ├── scoring-configs.ts    # fetchScoringConfigPresets() — GET /scoring-configs/presets (public)
│   │       ├── user-kits.ts          # User kit CRUD
│   │       └── index.ts              # apiFetch() base wrapper + ApiError
│   ├── store/
│   │   ├── rankings.ts               # Zustand: rankings state
│   │   ├── kits.ts                   # Zustand: kit weights + dirty tracking
│   │   └── auth.ts                   # Zustand: user session
│   ├── types/
│   │   └── supabase.ts               # Generated Supabase types (via CLI)
│   └── test/
│       └── setup.ts                  # Vitest setup — jest-dom matchers
├── middleware.ts                     # Session refresh + route protection
└── vitest.config.ts                  # Vitest + jsdom

packages/ui/
├── PlayerCard/
├── RankingsTable/
└── SuggestionPanel/                  # Used by both web + extension
```

---

## 2. Supabase Auth Setup

### Browser Client

```typescript
// apps/web/src/lib/supabase.ts
import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "@/types/supabase";

export const supabase = createBrowserClient<Database>(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
```

### Server Client Factory

```typescript
// apps/web/src/lib/supabase-server.ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { Database } from "@/types/supabase";

export function createSupabaseServerClient() {
  const cookieStore = cookies();
  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name) { return cookieStore.get(name)?.value; },
        set(name, value, options) { cookieStore.set({ name, value, ...options }); },
        remove(name, options) { cookieStore.set({ name, value: "", ...options }); },
      },
    }
  );
}
```

### Middleware (Route Protection)

```typescript
// apps/web/middleware.ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request: { headers: request.headers } });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { ... } }  // see docs/archive/phase-1-frontend.md for full implementation
  );

  const { data: { session } } = await supabase.auth.getSession();

  // Protect /dashboard routes
  if (!session && request.nextUrl.pathname.startsWith("/dashboard")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Redirect authenticated users away from auth pages
  if (session && request.nextUrl.pathname.startsWith("/login")) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return response;
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/signup"],
};
```

### OAuth Callback

```typescript
// apps/web/src/app/(auth)/callback/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase-server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = createSupabaseServerClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(`${origin}/dashboard`);
  }

  return NextResponse.redirect(`${origin}/login?error=auth_failed`);
}
```

---

## 3. Anonymous User Flow

- Anonymous users can build kits without signing in
- Session tracked by `pucklogic_session` cookie (UUID)
- Persistent banner: "Sign up to save this kit"
- On sign-up/login, the web app ultimately targets the backend auth/session contract (for example `POST /auth/register` if using direct backend routes) so session-keyed kits can be migrated to `user_id`
- Anonymous kits expire after 7 days (server-side cron)

---

## 4. Zustand Stores

### Rankings Store

```typescript
// apps/web/src/store/rankings.ts
import { create } from "zustand";

export interface RankedPlayer {
  player_id: string;
  name: string;
  team: string;
  default_position: string;          // NHL.com canonical position
  platform_positions: string[];       // platform-specific eligibility
  composite_rank: number;
  projected_fantasy_points: number | null;
  vorp: number | null;               // null if no league_profile_id provided
  schedule_score: number | null;
  off_night_games: number | null;
  source_count: number;
  projected_stats: {
    g: number | null; a: number | null; plus_minus: number | null;
    pim: number | null; ppg: number | null; ppa: number | null;
    ppp: number | null; shg: number | null; sha: number | null;
    shp: number | null; sog: number | null; fow: number | null;
    fol: number | null; hits: number | null; blocks: number | null;
    gp: number | null;
  };
  breakout_score?: number;
  regression_risk?: number;
}

export interface RankingsState {
  players: RankedPlayer[];
  isLoading: boolean;
  error: string | null;
  season: string;
  cached: boolean;
  computedAt: string | null;

  setSeason: (season: string) => void;
  setPlayers: (players: RankedPlayer[], cached: boolean, computedAt: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useRankingsStore = create<RankingsState>()((set) => ({
  players: [], isLoading: false, error: null, season: "2024-25",
  cached: false, computedAt: null,

  setSeason: (season) => set({ season }),
  setPlayers: (players, cached, computedAt) => set({ players, cached, computedAt, error: null }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error, isLoading: false }),
  reset: () => set({ players: [], isLoading: false, error: null }),
}));
```

### Kits Store

```typescript
// apps/web/src/store/kits.ts
import { create } from "zustand";

export interface WeightConfig {
  source_id: string;
  source_name: string;
  weight: number;    // 0–100; all enabled weights sum to 100
  enabled: boolean;
}

// user_kits are named source-weight presets only.
// Full league config (platform, scoring, roster) lives in league_profiles.
export interface UserKit {
  id: string;
  name: string;
  weights: WeightConfig[];
}

export interface KitsState {
  activeKit: UserKit | null;
  weights: WeightConfig[];
  isDirty: boolean;  // unsaved local changes

  setActiveKit: (kit: UserKit) => void;
  updateWeight: (source_id: string, weight: number) => void;
  toggleSource: (source_id: string) => void;
  resetWeights: () => void;
  markSaved: () => void;
}

export const useKitsStore = create<KitsState>()((set, get) => ({
  activeKit: null, weights: [], isDirty: false,

  setActiveKit: (kit) => set({ activeKit: kit, weights: kit.weights, isDirty: false }),

  updateWeight: (source_id, weight) => {
    const { weights } = get();
    const enabled = weights.filter((w) => w.enabled);
    const remaining = 100 - weight;
    const others = enabled.filter((w) => w.source_id !== source_id);
    const othersTotal = others.reduce((sum, w) => sum + w.weight, 0);

    const updated = weights.map((w) => {
      if (w.source_id === source_id) return { ...w, weight };
      if (!w.enabled || othersTotal === 0) return w;
      return { ...w, weight: (w.weight / othersTotal) * remaining };
    });
    set({ weights: updated, isDirty: true });
  },

  toggleSource: (source_id) => {
    const { weights } = get();
    const updated = weights.map((w) =>
      w.source_id === source_id ? { ...w, enabled: !w.enabled } : w
    );
    const enabledTotal = updated.filter((w) => w.enabled).reduce((s, w) => s + w.weight, 0);
    const normalized = updated.map((w) => ({
      ...w,
      weight: w.enabled && enabledTotal > 0 ? (w.weight / enabledTotal) * 100 : w.weight,
    }));
    set({ weights: normalized, isDirty: true });
  },

  resetWeights: () => {
    const { activeKit } = get();
    if (activeKit) set({ weights: activeKit.weights, isDirty: false });
  },

  markSaved: () => set({ isDirty: false }),
}));
```

---

## 5. Data Fetching (SWR)

```typescript
// apps/web/src/lib/api/rankings.ts
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export interface RankingsParams {
  season: string;
  source_weights: Record<string, number>;   // { source_id: weight }
  scoring_config_id: string;
  platform: string;                          // "espn" | "yahoo" | "fantrax"
  league_profile_id?: string;               // optional; enables VORP
}

export function useRankings(params: RankingsParams | null) {
  const key = params
    ? `/rankings/compute`
    : null;
  const { data, error, isLoading, mutate } = useSWR(
    key ? [key, params] : null,
    ([url, p]) => fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p),
    }).then((r) => r.json()),
    { revalidateOnFocus: false }
  );
  return { rankings: data, error, isLoading, mutate };
}

export function useSources() {
  return useSWR("/sources", fetcher);
}
```

**Server Components** use `fetch` directly (no SWR). **Client Components** use SWR hooks for interactive data.

If the Next.js app introduces local route handlers or proxy endpoints, keep them aligned with the canonical backend route names documented in `docs/backend-reference.md` instead of inventing a parallel API contract.

---

## 6. Key Components

### WeightControls

- Location: `apps/web/src/components/WeightControls.tsx`
- Uses: `useKitsStore` for weight state, shadcn/ui `Slider` + `Switch`
- Behavior: sliders auto-normalize on change; "Unsaved changes" badge when `isDirty`
- Triggers re-compute by calling `mutate()` from SWR rankings hook

### RankingsTable

- Location: `apps/web/src/components/RankingsTable.tsx` + `packages/ui/RankingsTable/`
- Columns: Rank, Player, Team, Pos (platform positions), Fantasy Pts, FP/GP, VORP, Positional Rank, GP, Off Nights, full projected stat columns, Trends badge
- Null stats displayed as `—` (never `0` when unprojected)
- Filterable: position (All/C/LW/RW/D/G), team
- Sortable: all numeric columns (click header)
- Trends badge: shown when `breakout_score > 0.6` or `regression_risk > 0.6`

### ScoringConfigPanel

- Location: `apps/web/src/components/ScoringConfigPanel.tsx`
- Presets: ESPN Standard H2H, Yahoo Standard, Rotisserie, Custom
- Custom editor: inputs per stat category (goals, assists, PPP, SOG, hits, blocks)
- Shows both **raw projected stats** and **fantasy points** side-by-side in rankings

### ExportPanel

- Location: `apps/web/src/components/ExportPanel.tsx`
- Triggers `POST /exports/generate`
- Current launch path assumes synchronous export generation/response rather than polling a queued export job
- If queued exports are introduced later, update both this reference and the backend reference together

### TrendsPanel (Phase 3)

- Location: `apps/web/src/components/TrendsPanel.tsx`
- Shows: breakout_score (0–1), regression_risk (0–1), confidence
- SHAP explainer: horizontal bar chart of top feature contributions
- Displays both raw projected stats AND fantasy points for context

---

## 7. Scoring Translation Display

```typescript
// Dashboard shows both projected stats and fantasy points side-by-side.
// Stats are sourced from RankedPlayer.projected_stats — null means no source projected it.
interface PlayerScoreDisplay {
  projected_stats: RankedPlayer["projected_stats"];  // full stat set, nulls displayed as —
  projected_fantasy_points: number | null;           // sum(projected_stat × scoring_weight)
  vorp: number | null;                               // null when no league_profile_id provided
  schedule_score: number | null;
  off_night_games: number | null;
}
```

---

## 8. Stripe Checkout Flow

```typescript
// Export or draft session purchase → redirect to Stripe
async function startCheckout(priceId: string, successPath: string) {
  const res = await fetch("/stripe/create-checkout-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ price_id: priceId, success_path: successPath }),
  });
  const { url } = await res.json();
  window.location.href = url;  // redirect to Stripe Checkout
}
```

No payment UI in the extension — all purchases happen on the web app.

---

## 9. Environment Variables (Frontend)

```bash
# .env.local (Next.js — never commit)
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_SITE_URL=https://pucklogic.com  # or http://localhost:3000
NEXT_PUBLIC_API_URL=https://api.pucklogic.com  # FastAPI backend
```

---

## 10. Testing Conventions

- **Framework:** Vitest + React Testing Library
- **Config:** `apps/web/vitest.config.ts` — jsdom env, globals enabled, v8 coverage
- **Setup:** `apps/web/src/test/setup.ts` — imports `@testing-library/jest-dom`
- **Location:** Co-locate tests in `__tests__/` next to the source file
  - e.g. `src/components/__tests__/RankingsTable.test.tsx`
  - e.g. `src/lib/api/__tests__/rankings.test.ts`
- **Mocking:** `vi.spyOn` / `vi.mock` for API calls — never hit real network or Supabase
- **Run:** `pnpm test` (single pass), `pnpm test:watch`, `pnpm test:coverage`
- TDD required: write failing test before implementation

---

## 11. Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Router | App Router (Next.js 14+) | Server Components, streaming, layout nesting |
| State | Zustand | Lightweight, no boilerplate vs Redux |
| Data fetching | SWR (client), Server Components (SSR) | SWR for cache-and-revalidate; SC for initial page load |
| Auth | `@supabase/ssr` + middleware | Handles cookie-based sessions + route protection |
| Styling | Tailwind CSS + shadcn/ui | Utility-first, accessible components |
| Anonymous kits | session_token cookie | Allows free trial without account friction |
| Mobile | Mobile-responsive (Tailwind breakpoints) | Draft monitor is desktop-only; dashboard is responsive |
