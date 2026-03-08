# PuckLogic Phase 2 — Frontend Implementation

## Aggregation Dashboard — Source Weights UI, Rankings Table, Exports, Stripe Checkout

**Timeline:** May – June 2026 (Phase 2)
**Target Release:** v1.0 (September 2026)
**Backend Reference:** `docs/phase-2-backend.md`

---

## Overview

Phase 2 frontend delivers the **Aggregation Dashboard** — the core user-facing product for the free rankings tier. Users configure source weights, trigger composite rankings computation, browse the sortable/filterable results table, and download PDF/Excel exports. Pro subscription management is handled via Stripe Checkout.

**Deliverables:**
1. ✅ Source weight UI (sliders per source, auto-normalize to 100%)
2. ✅ Composite `RankingsTable` (sortable, filterable by position/team)
3. ✅ `rankingsSlice` + `kitsSlice` Zustand store slices
4. ✅ SWR data fetching from `/api/rankings/compute`
5. ✅ Export download flow (PDF and Excel)
6. ✅ Stripe checkout redirect (Pro plan)
7. ✅ Test coverage (Vitest + React Testing Library)

---

## 1. Zustand Store Slices

### 1.1 Rankings Slice

**Location:** `apps/web/src/store/rankings.ts`

```typescript
import { create } from "zustand";

export interface RankedPlayer {
  player_id: string;
  name: string;
  team: string;
  position: string;
  composite_rank: number;
  composite_score: number;
  fantasy_pts: number;
  vorp: number;
  source_ranks: Record<string, number>;  // { dobber: 12, nhl_com: 14, ... }
}

export interface RankingsState {
  players: RankedPlayer[];
  isLoading: boolean;
  error: string | null;
  season: string;
  cached: boolean;
  computedAt: string | null;

  // Actions
  setSeason: (season: string) => void;
  setPlayers: (players: RankedPlayer[], cached: boolean, computedAt: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  players: [],
  isLoading: false,
  error: null,
  season: "2024-25",
  cached: false,
  computedAt: null,
};

export const useRankingsStore = create<RankingsState>()((set) => ({
  ...initialState,

  setSeason: (season) => set({ season }),

  setPlayers: (players, cached, computedAt) =>
    set({ players, cached, computedAt, error: null }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error, isLoading: false }),

  reset: () => set(initialState),
}));
```

### 1.2 Kits Slice

**Location:** `apps/web/src/store/kits.ts`

```typescript
import { create } from "zustand";

export interface WeightConfig {
  source_id: string;
  source_name: string;
  weight: number;    // 0–100, sum of all enabled weights = 100
  enabled: boolean;
}

export interface UserKit {
  id: string;
  name: string;
  league_format: "points" | "roto" | "head_to_head";
  scoring_settings: Record<string, number>;
  weights: WeightConfig[];
}

export interface KitsState {
  activeKit: UserKit | null;
  weights: WeightConfig[];
  isDirty: boolean;   // true when there are unsaved local changes

  // Actions
  setActiveKit: (kit: UserKit) => void;
  updateWeight: (source_id: string, weight: number) => void;
  toggleSource: (source_id: string) => void;
  resetWeights: () => void;
  markSaved: () => void;
}

export const useKitsStore = create<KitsState>()((set, get) => ({
  activeKit: null,
  weights: [],
  isDirty: false,

  setActiveKit: (kit) =>
    set({ activeKit: kit, weights: kit.weights, isDirty: false }),

  updateWeight: (source_id, weight) => {
    const { weights } = get();
    const enabled = weights.filter((w) => w.enabled);
    const target = enabled.find((w) => w.source_id === source_id);
    if (!target) return;

    // Distribute remaining weight proportionally across other enabled sources
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
    // Re-normalize after toggle
    const enabledTotal = updated
      .filter((w) => w.enabled)
      .reduce((sum, w) => sum + w.weight, 0);

    const normalized = updated.map((w) => ({
      ...w,
      weight: w.enabled && enabledTotal > 0
        ? (w.weight / enabledTotal) * 100
        : w.enabled ? 100 : w.weight,
    }));

    set({ weights: normalized, isDirty: true });
  },

  resetWeights: () => {
    const { activeKit } = get();
    if (activeKit) {
      set({ weights: activeKit.weights, isDirty: false });
    }
  },

  markSaved: () => set({ isDirty: false }),
}));
```

---

## 2. Source Weight UI

### 2.1 WeightControls Component

**Location:** `apps/web/src/components/WeightControls.tsx`

```typescript
import { useKitsStore } from "@/store/kits";
import { useRankings } from "@/lib/api/rankings";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";

export function WeightControls() {
  const { weights, isDirty, updateWeight, toggleSource, resetWeights, activeKit } =
    useKitsStore();
  const { mutate: recompute } = useRankings(activeKit?.id ?? "", "2024-25");

  const handleSaveKit = async () => {
    if (!activeKit) return;
    await fetch(`/api/kits/${activeKit.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weights }),
    });
    useKitsStore.getState().markSaved();
  };

  const handleCompute = () => {
    recompute(undefined, { revalidate: true });
  };

  return (
    <div className="space-y-4 p-4 bg-white rounded-lg border border-gray-200">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Source Weights</h2>
        {isDirty && (
          <span className="text-sm text-amber-600 font-medium">Unsaved changes</span>
        )}
      </div>

      <div className="space-y-3">
        {weights.map((w) => (
          <div key={w.source_id} className="flex items-center gap-4">
            <Switch
              checked={w.enabled}
              onCheckedChange={() => toggleSource(w.source_id)}
              aria-label={`Toggle ${w.source_name}`}
            />
            <span className="w-40 text-sm font-medium truncate">{w.source_name}</span>
            <Slider
              disabled={!w.enabled}
              value={[w.weight]}
              onValueChange={([val]) => updateWeight(w.source_id, val)}
              min={0}
              max={100}
              step={1}
              className="flex-1"
              aria-label={`${w.source_name} weight`}
            />
            <span className="w-12 text-right text-sm tabular-nums">
              {w.enabled ? `${Math.round(w.weight)}%` : "—"}
            </span>
          </div>
        ))}
      </div>

      <div className="flex gap-2 pt-2">
        <Button variant="outline" size="sm" onClick={resetWeights} disabled={!isDirty}>
          Reset
        </Button>
        <Button variant="outline" size="sm" onClick={handleSaveKit} disabled={!isDirty}>
          Save Kit
        </Button>
        <Button size="sm" onClick={handleCompute} className="ml-auto">
          Compute Rankings
        </Button>
      </div>
    </div>
  );
}
```

### 2.2 Weight Normalization Invariant

The sum of all **enabled** source weights must always equal exactly 100%. The `updateWeight` action in `kitsSlice` enforces this by proportionally redistributing the remaining weight across other enabled sources whenever any slider moves. Disabled sources retain their last weight value (shown greyed out) so re-enabling them restores a sensible starting point.

---

## 3. Rankings Table

### 3.1 RankingsTable Component

**Location:** `apps/web/src/components/RankingsTable.tsx`

```typescript
import { useState, useMemo } from "react";
import { useRankingsStore, RankedPlayer } from "@/store/rankings";
import { useKitsStore } from "@/store/kits";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

type SortKey = keyof Pick<RankedPlayer, "composite_rank" | "fantasy_pts" | "vorp" | "name">;
type SortDir = "asc" | "desc";

export function RankingsTable() {
  const { players } = useRankingsStore();
  const { weights } = useKitsStore();

  const [search, setSearch] = useState("");
  const [posFilter, setPosFilter] = useState<"all" | "C" | "LW" | "RW" | "D" | "G">("all");
  const [teamFilter, setTeamFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("composite_rank");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);

  const PAGE_SIZE = 50;

  const enabledSources = useMemo(
    () => weights.filter((w) => w.enabled).map((w) => w.source_id),
    [weights]
  );

  const allTeams = useMemo(
    () => [...new Set(players.map((p) => p.team))].sort(),
    [players]
  );

  const filtered = useMemo(() => {
    let rows = players;
    if (search) {
      rows = rows.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()));
    }
    if (posFilter !== "all") {
      rows = rows.filter((p) => p.position === posFilter);
    }
    if (teamFilter !== "all") {
      rows = rows.filter((p) => p.team === teamFilter);
    }
    return rows;
  }, [players, search, posFilter, teamFilter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc"
        ? (av as number) - (bv as number)
        : (bv as number) - (av as number);
    });
  }, [filtered, sortKey, sortDir]);

  const paginated = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const SortIndicator = ({ col }: { col: SortKey }) =>
    sortKey === col ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Search player..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-48"
        />
        <Select value={posFilter} onValueChange={(v) => { setPosFilter(v as typeof posFilter); setPage(1); }}>
          <SelectTrigger className="w-28">
            <SelectValue placeholder="Position" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="C">C</SelectItem>
            <SelectItem value="LW">LW</SelectItem>
            <SelectItem value="RW">RW</SelectItem>
            <SelectItem value="D">D</SelectItem>
            <SelectItem value="G">G</SelectItem>
          </SelectContent>
        </Select>
        <Select value={teamFilter} onValueChange={(v) => { setTeamFilter(v); setPage(1); }}>
          <SelectTrigger className="w-28">
            <SelectValue placeholder="Team" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Teams</SelectItem>
            {allTeams.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50">
              <TableHead
                className="cursor-pointer select-none w-12"
                onClick={() => handleSort("composite_rank")}
              >
                #{SortIndicator({ col: "composite_rank" })}
              </TableHead>
              <TableHead
                className="cursor-pointer select-none"
                onClick={() => handleSort("name")}
              >
                Player{SortIndicator({ col: "name" })}
              </TableHead>
              <TableHead>Team</TableHead>
              <TableHead>Pos</TableHead>
              <TableHead
                className="cursor-pointer select-none text-right"
                onClick={() => handleSort("fantasy_pts")}
              >
                Fantasy Pts{SortIndicator({ col: "fantasy_pts" })}
              </TableHead>
              <TableHead
                className="cursor-pointer select-none text-right"
                onClick={() => handleSort("vorp")}
              >
                VORP{SortIndicator({ col: "vorp" })}
              </TableHead>
              <TableHead className="text-center text-gray-400 text-xs">Breakout</TableHead>
              <TableHead className="text-center text-gray-400 text-xs">Regression</TableHead>
              {enabledSources.map((src) => (
                <TableHead key={src} className="text-right text-xs">
                  {src}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginated.map((player, idx) => (
              <TableRow
                key={player.player_id}
                className="hover:bg-gray-50 cursor-pointer"
              >
                <TableCell className="font-mono text-sm text-gray-500">
                  {(page - 1) * PAGE_SIZE + idx + 1}
                </TableCell>
                <TableCell className="font-medium">{player.name}</TableCell>
                <TableCell className="text-sm">{player.team}</TableCell>
                <TableCell className="text-sm">{player.position}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {player.fantasy_pts.toFixed(1)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {player.vorp >= 0 ? "+" : ""}{player.vorp.toFixed(1)}
                </TableCell>
                {/* Breakout/regression badges — populated in Phase 3 */}
                <TableCell className="text-center text-gray-300 text-xs">—</TableCell>
                <TableCell className="text-center text-gray-300 text-xs">—</TableCell>
                {enabledSources.map((src) => (
                  <TableCell key={src} className="text-right tabular-nums text-sm">
                    {player.source_ranks[src] ?? "—"}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          {sorted.length} players · page {page} of {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40"
          >
            Previous
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 3.2 Column Reference

| Column | Source | Notes |
|--------|--------|-------|
| `#` | `composite_rank` | Position in final sorted list |
| Player | `name` | Sortable |
| Team | `team` | Filterable via dropdown |
| Pos | `position` | Filterable (C/LW/RW/D/G) |
| Fantasy Pts | `fantasy_pts` | Sortable; points-league output |
| VORP | `vorp` | Sortable; value over replacement player |
| Breakout | Phase 3 | Empty in Phase 2; populated by ML layer |
| Regression | Phase 3 | Empty in Phase 2; populated by ML layer |
| `{source} Rank` | `source_ranks` | One column per enabled source; dynamically rendered |

---

## 4. SWR Data Fetching

### 4.1 Rankings Hook

**Location:** `apps/web/src/lib/api/rankings.ts`

```typescript
import useSWR from "swr";
import { useRankingsStore } from "@/store/rankings";
import { useKitsStore } from "@/store/kits";

interface RankingsResponse {
  players: RankedPlayer[];
  cached: boolean;
  computed_at: string;
}

async function computeRankings(
  url: string,
  kitId: string,
  season: string,
  token: string,
  forceRefresh = false,
): Promise<RankingsResponse> {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      user_kit_id: kitId,
      season,
      force_refresh: forceRefresh,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Rankings request failed: ${res.status}`);
  }
  return res.json();
}

export function useRankings(kitId: string, season: string) {
  const { setPlayers, setLoading, setError } = useRankingsStore();

  const swr = useSWR(
    kitId ? ["/api/rankings/compute", kitId, season] : null,
    ([url, kid, s]) => computeRankings(url, kid, s, getToken()),
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,   // 1 minute client-side dedup
      onSuccess(data) {
        setPlayers(data.players, data.cached, data.computed_at);
      },
      onError(err) {
        setError(err.message);
      },
    },
  );

  return swr;
}
```

### 4.2 Force Refresh

When the user clicks "Compute Rankings" after changing weights, the hook is called with `force_refresh: true`. This is exposed via the SWR `mutate` function with a custom fetcher argument:

```typescript
const { mutate } = useRankings(kit.id, season);

// In WeightControls onClick handler:
await mutate(
  computeRankings("/api/rankings/compute", kit.id, season, token, true),
  { revalidate: false }
);
```

---

## 5. Export Download Flow

### 5.1 ExportButton Component

**Location:** `apps/web/src/components/ExportButton.tsx`

```typescript
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useKitsStore } from "@/store/kits";
import { redirectToCheckout } from "@/lib/api/stripe";

interface ExportButtonProps {
  format: "pdf" | "xlsx";
  season: string;
  isPro: boolean;
}

export function ExportButton({ format, season, isPro }: ExportButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { activeKit } = useKitsStore();

  const handleExport = async () => {
    if (!isPro) {
      await redirectToCheckout(process.env.NEXT_PUBLIC_STRIPE_PRO_PRICE_ID!);
      return;
    }

    if (!activeKit) return;
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        format,
        user_kit_id: activeKit.id,
        season,
      });
      const res = await fetch(`/api/exports/generate?${params}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });

      if (!res.ok) throw new Error(`Export failed: ${res.status}`);

      const { url, filename } = await res.json();

      // Trigger browser download
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <Button
        variant="outline"
        size="sm"
        onClick={handleExport}
        disabled={isLoading || !activeKit}
      >
        {isLoading ? (
          <span className="flex items-center gap-2">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
            Generating...
          </span>
        ) : (
          isPro
            ? `Export ${format.toUpperCase()}`
            : `Export ${format.toUpperCase()} (Pro)`
        )}
      </Button>
      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
    </div>
  );
}
```

### 5.2 Export Flow Summary

1. User clicks "Export PDF" or "Export Excel"
2. If not a Pro subscriber → `redirectToCheckout` sends user to Stripe Checkout
3. If Pro → `GET /api/exports/generate?format=pdf&...` with JWT
4. Backend computes rankings (from cache) → generates file → uploads to Supabase Storage → returns signed URL
5. Frontend receives signed URL → triggers `<a>` click for browser download
6. Loading spinner displayed during generation (typically 3–10 seconds for PDF)

---

## 6. Stripe Checkout

### 6.1 Billing Page

**Location:** `apps/web/src/app/(dashboard)/settings/billing/page.tsx`

```typescript
import { redirectToCheckout } from "@/lib/api/stripe";
import { useSubscription } from "@/lib/api/subscriptions";
import { Button } from "@/components/ui/button";

export default function BillingPage() {
  const { subscription, isLoading } = useSubscription();

  if (isLoading) return <p>Loading...</p>;

  const isPro = subscription?.plan === "pro" && subscription?.status === "active";

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Subscription</h1>
        <p className="text-sm text-gray-600 mt-1">
          Manage your PuckLogic plan.
        </p>
      </div>

      <div className="p-6 rounded-lg border border-gray-200 bg-white space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-semibold">{isPro ? "Pro" : "Free"} Plan</p>
            <p className="text-sm text-gray-500">
              {isPro
                ? `Renews ${new Date(subscription.expires_at * 1000).toLocaleDateString()}`
                : "Upgrade to unlock PDF/Excel exports"}
            </p>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
            isPro ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"
          }`}>
            {isPro ? "Active" : "Free"}
          </span>
        </div>

        {!isPro && (
          <Button
            onClick={() =>
              redirectToCheckout(process.env.NEXT_PUBLIC_STRIPE_PRO_PRICE_ID!)
            }
            className="w-full"
          >
            Upgrade to Pro — $X/month
          </Button>
        )}
      </div>
    </div>
  );
}
```

### 6.2 Stripe Helper

**Location:** `apps/web/src/lib/api/stripe.ts`

```typescript
export async function redirectToCheckout(priceId: string): Promise<void> {
  const res = await fetch("/api/stripe/create-checkout-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ price_id: priceId }),
  });

  if (!res.ok) throw new Error("Failed to create Stripe checkout session");

  const { url } = await res.json();
  window.location.href = url;
}
```

### 6.3 Next.js API Route for Checkout Session

**Location:** `apps/web/src/app/api/stripe/create-checkout-session/route.ts`

```typescript
import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST(request: NextRequest) {
  const { price_id } = await request.json();

  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    payment_method_types: ["card"],
    line_items: [{ price: price_id, quantity: 1 }],
    success_url: `${process.env.NEXT_PUBLIC_APP_URL}/settings/billing?success=true`,
    cancel_url: `${process.env.NEXT_PUBLIC_APP_URL}/settings/billing?cancelled=true`,
  });

  return NextResponse.json({ url: session.url });
}
```

### 6.4 Post-Checkout Subscription Polling

After redirect back from Stripe, the billing page detects `?success=true` in the URL and polls the `/api/subscriptions/me` endpoint until the Stripe webhook has updated the `subscriptions` table (typically <5 seconds):

```typescript
// In BillingPage: detect post-checkout return
const searchParams = useSearchParams();
const isSuccess = searchParams.get("success") === "true";

useEffect(() => {
  if (!isSuccess) return;
  // SWR refreshInterval polls every 2s until isPro becomes true
  const interval = setInterval(() => {
    mutateSubscription();
  }, 2000);
  return () => clearInterval(interval);
}, [isSuccess, mutateSubscription]);
```

---

## 7. Dashboard Page Layout

### 7.1 Main Dashboard Page

**Location:** `apps/web/src/app/(dashboard)/dashboard/page.tsx`

```typescript
import { WeightControls } from "@/components/WeightControls";
import { RankingsTable } from "@/components/RankingsTable";
import { ExportButton } from "@/components/ExportButton";
import { useRankings } from "@/lib/api/rankings";
import { useKitsStore } from "@/store/kits";
import { useRankingsStore } from "@/store/rankings";
import { useSubscription } from "@/lib/api/subscriptions";

export default function DashboardPage() {
  const { activeKit, season } = useKitsStore((s) => ({ activeKit: s.activeKit, season: "2024-25" }));
  const { isLoading, error } = useRankings(activeKit?.id ?? "", "2024-25");
  const { players, computedAt, cached } = useRankingsStore();
  const { subscription } = useSubscription();
  const isPro = subscription?.plan === "pro" && subscription?.status === "active";

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start gap-6">
        {/* Left: weight controls */}
        <div className="w-80 flex-shrink-0">
          <WeightControls />
        </div>

        {/* Right: rankings */}
        <div className="flex-1 min-w-0 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">Rankings</h1>
              {computedAt && (
                <p className="text-xs text-gray-500">
                  {cached ? "Cached · " : ""}
                  Updated {new Date(computedAt).toLocaleTimeString()}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <ExportButton format="pdf" season="2024-25" isPro={isPro} />
              <ExportButton format="xlsx" season="2024-25" isPro={isPro} />
            </div>
          </div>

          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
              Computing rankings...
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {error}
            </div>
          )}

          {players.length > 0 && <RankingsTable />}

          {!isLoading && !error && players.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              Select a kit and click <strong>Compute Rankings</strong> to get started.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

---

## 8. Testing

### 8.1 WeightControls Tests

**Location:** `apps/web/src/components/__tests__/WeightControls.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WeightControls } from "@/components/WeightControls";
import { useKitsStore } from "@/store/kits";

const mockKit = {
  id: "kit-1",
  name: "My Kit",
  league_format: "points" as const,
  scoring_settings: {},
  weights: [
    { source_id: "nhl_com", source_name: "NHL.com", weight: 50, enabled: true },
    { source_id: "dobber", source_name: "Dobber Hockey", weight: 50, enabled: true },
  ],
};

beforeEach(() => {
  useKitsStore.setState({ activeKit: mockKit, weights: mockKit.weights, isDirty: false });
});

describe("WeightControls", () => {
  it("renders one row per source", () => {
    render(<WeightControls />);
    expect(screen.getByText("NHL.com")).toBeInTheDocument();
    expect(screen.getByText("Dobber Hockey")).toBeInTheDocument();
  });

  it("shows unsaved changes banner when isDirty", () => {
    useKitsStore.setState({ isDirty: true });
    render(<WeightControls />);
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  it("reset button restores original weights", async () => {
    useKitsStore.setState({ isDirty: true });
    const user = userEvent.setup();
    render(<WeightControls />);
    await user.click(screen.getByText("Reset"));
    expect(useKitsStore.getState().isDirty).toBe(false);
  });
});
```

### 8.2 RankingsTable Tests

**Location:** `apps/web/src/components/__tests__/RankingsTable.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RankingsTable } from "@/components/RankingsTable";
import { useRankingsStore } from "@/store/rankings";
import { useKitsStore } from "@/store/kits";

const mockPlayers = [
  { player_id: "p1", name: "Connor McDavid", team: "EDM", position: "C",
    composite_rank: 1, composite_score: 0.98, fantasy_pts: 287.5, vorp: 142.3,
    source_ranks: { nhl_com: 1 } },
  { player_id: "p2", name: "Nathan MacKinnon", team: "COL", position: "C",
    composite_rank: 2, composite_score: 0.96, fantasy_pts: 274.1, vorp: 128.9,
    source_ranks: { nhl_com: 2 } },
  { player_id: "p3", name: "Cale Makar", team: "COL", position: "D",
    composite_rank: 3, composite_score: 0.93, fantasy_pts: 218.7, vorp: 92.4,
    source_ranks: { nhl_com: 3 } },
];

beforeEach(() => {
  useRankingsStore.setState({ players: mockPlayers });
  useKitsStore.setState({
    weights: [{ source_id: "nhl_com", source_name: "NHL.com", weight: 100, enabled: true }],
  });
});

describe("RankingsTable", () => {
  it("renders all players", () => {
    render(<RankingsTable />);
    expect(screen.getByText("Connor McDavid")).toBeInTheDocument();
    expect(screen.getByText("Nathan MacKinnon")).toBeInTheDocument();
    expect(screen.getByText("Cale Makar")).toBeInTheDocument();
  });

  it("filters by position", async () => {
    const user = userEvent.setup();
    render(<RankingsTable />);

    const posSelect = screen.getByRole("combobox", { name: /position/i });
    await user.click(posSelect);
    await user.click(screen.getByText("D"));

    expect(screen.getByText("Cale Makar")).toBeInTheDocument();
    expect(screen.queryByText("Connor McDavid")).not.toBeInTheDocument();
  });

  it("filters by player name search", async () => {
    const user = userEvent.setup();
    render(<RankingsTable />);

    const search = screen.getByPlaceholderText("Search player...");
    await user.type(search, "Makar");

    expect(screen.getByText("Cale Makar")).toBeInTheDocument();
    expect(screen.queryByText("Connor McDavid")).not.toBeInTheDocument();
  });

  it("sorts by Fantasy Pts descending on column header click", async () => {
    const user = userEvent.setup();
    render(<RankingsTable />);

    const fptHeader = screen.getByText(/Fantasy Pts/);
    await user.click(fptHeader);
    await user.click(fptHeader); // second click = descending

    const rows = screen.getAllByRole("row");
    // First data row should be McDavid (highest pts)
    expect(rows[1]).toHaveTextContent("Connor McDavid");
  });
});
```

### 8.3 Kits Store Tests

**Location:** `apps/web/src/store/__tests__/kits.test.ts`

```typescript
import { useKitsStore } from "@/store/kits";

const mockKit = {
  id: "kit-1",
  name: "Test Kit",
  league_format: "points" as const,
  scoring_settings: {},
  weights: [
    { source_id: "nhl_com", source_name: "NHL.com", weight: 60, enabled: true },
    { source_id: "dobber", source_name: "Dobber Hockey", weight: 40, enabled: true },
  ],
};

beforeEach(() => {
  useKitsStore.setState({ activeKit: mockKit, weights: mockKit.weights, isDirty: false });
});

describe("kitsStore", () => {
  it("setActiveKit loads weights and clears isDirty", () => {
    useKitsStore.getState().setActiveKit(mockKit);
    expect(useKitsStore.getState().weights).toEqual(mockKit.weights);
    expect(useKitsStore.getState().isDirty).toBe(false);
  });

  it("updateWeight keeps enabled weights summing to 100", () => {
    useKitsStore.getState().updateWeight("nhl_com", 70);
    const { weights } = useKitsStore.getState();
    const enabledTotal = weights
      .filter((w) => w.enabled)
      .reduce((sum, w) => sum + w.weight, 0);
    expect(enabledTotal).toBeCloseTo(100, 1);
  });

  it("updateWeight sets isDirty", () => {
    useKitsStore.getState().updateWeight("nhl_com", 70);
    expect(useKitsStore.getState().isDirty).toBe(true);
  });

  it("resetWeights restores original kit weights", () => {
    useKitsStore.getState().updateWeight("nhl_com", 80);
    useKitsStore.getState().resetWeights();
    expect(useKitsStore.getState().weights).toEqual(mockKit.weights);
    expect(useKitsStore.getState().isDirty).toBe(false);
  });

  it("toggleSource disables a source and redistributes weight", () => {
    useKitsStore.getState().toggleSource("dobber");
    const { weights } = useKitsStore.getState();
    const dobber = weights.find((w) => w.source_id === "dobber")!;
    expect(dobber.enabled).toBe(false);

    const enabledTotal = weights
      .filter((w) => w.enabled)
      .reduce((sum, w) => sum + w.weight, 0);
    expect(enabledTotal).toBeCloseTo(100, 1);
  });
});
```

### 8.4 Rankings API Hook Tests

**Location:** `apps/web/src/lib/api/__tests__/rankings.test.ts`

```typescript
import { renderHook, waitFor } from "@testing-library/react";
import { useRankings } from "@/lib/api/rankings";
import { useRankingsStore } from "@/store/rankings";
import { vi } from "vitest";

const mockResponse = {
  players: [
    {
      player_id: "p1", name: "Connor McDavid", team: "EDM", position: "C",
      composite_rank: 1, composite_score: 0.98, fantasy_pts: 287.5, vorp: 142.3,
      source_ranks: { nhl_com: 1 },
    },
  ],
  cached: true,
  computed_at: "2026-06-01T12:00:00Z",
};

beforeEach(() => {
  global.fetch = vi.fn();
  useRankingsStore.setState({ players: [], isLoading: false, error: null });
});

describe("useRankings", () => {
  it("posts correct body and populates store on success", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const { } = renderHook(() => useRankings("kit-1", "2024-25"));

    await waitFor(() => {
      expect(useRankingsStore.getState().players).toHaveLength(1);
      expect(useRankingsStore.getState().players[0].name).toBe("Connor McDavid");
    });

    const [, options] = vi.mocked(global.fetch).mock.calls[0];
    const body = JSON.parse((options as RequestInit).body as string);
    expect(body).toMatchObject({ user_kit_id: "kit-1", season: "2024-25" });
  });

  it("sets error state on failed response", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Internal Server Error" }),
    } as Response);

    renderHook(() => useRankings("kit-1", "2024-25"));

    await waitFor(() => {
      expect(useRankingsStore.getState().error).toBeTruthy();
    });
  });

  it("does not fetch when kitId is empty", async () => {
    renderHook(() => useRankings("", "2024-25"));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
```

---

## 9. Deployment Checklist

- [ ] `NEXT_PUBLIC_STRIPE_PRO_PRICE_ID` set in Vercel environment
- [ ] `STRIPE_SECRET_KEY` set in Vercel environment (server-only)
- [ ] `NEXT_PUBLIC_APP_URL` set to production URL for Stripe redirect
- [ ] Supabase Auth provider configured; JWT passed in all API requests
- [ ] shadcn/ui components installed: `slider`, `switch`, `select`, `table`, `dialog`, `button`
- [ ] SWR installed: `pnpm add swr`
- [ ] Zustand installed: `pnpm add zustand`
- [ ] All Vitest tests passing with >85% coverage
- [ ] RankingsTable renders correctly on mobile (horizontal scroll enabled)
- [ ] Export buttons hidden / show Pro gate for free-tier users

---

## 10. Performance Considerations

| Aspect | Target | Strategy |
|--------|--------|----------|
| Initial rankings fetch | <3s | SWR + backend Redis cache |
| Table render (500 players) | <200ms | Memoized filter/sort, no virtualization needed at 500 rows |
| Slider interaction | <16ms | Zustand state update; no re-render of table |
| Export trigger to download | <15s | Loading spinner shown; backend PDF runs async |
| Page bundle size | <100kB gzipped | shadcn/ui tree-shaking; lazy-load PlayerDrawer |

---

## Appendix: Key Files

| File | Purpose |
|------|---------|
| `apps/web/src/app/(dashboard)/dashboard/page.tsx` | Main rankings dashboard page |
| `apps/web/src/app/(dashboard)/settings/billing/page.tsx` | Stripe subscription management |
| `apps/web/src/app/api/stripe/create-checkout-session/route.ts` | Next.js API route for Stripe Checkout |
| `apps/web/src/components/WeightControls.tsx` | Source weight sliders with auto-normalize |
| `apps/web/src/components/RankingsTable.tsx` | Sortable/filterable rankings table |
| `apps/web/src/components/ExportButton.tsx` | PDF/Excel download with Pro gate |
| `apps/web/src/store/rankings.ts` | `RankingsState` — players, loading, error |
| `apps/web/src/store/kits.ts` | `KitsState` — weights, isDirty, normalization logic |
| `apps/web/src/lib/api/rankings.ts` | `useRankings` SWR hook |
| `apps/web/src/lib/api/stripe.ts` | `redirectToCheckout` helper |
| `apps/web/src/components/__tests__/WeightControls.test.tsx` | Slider and normalization tests |
| `apps/web/src/components/__tests__/RankingsTable.test.tsx` | Render, filter, sort tests |
| `apps/web/src/store/__tests__/kits.test.ts` | Weight normalization and toggle invariant tests |
| `apps/web/src/lib/api/__tests__/rankings.test.ts` | SWR hook fetch / error state tests |

---

*See also: `docs/phase-2-backend.md` (rankings engine, cache, Celery, exports, Stripe webhook)*
