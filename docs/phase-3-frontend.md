# PuckLogic Phase 3 — Frontend Implementation

## ML Trends Engine (Layer 1) — SHAP Explainability UI

**Timeline:** April – July 2026 (Phase 3)
**Target Release:** v1.0 (September 2026)
**Backend Reference:** `docs/phase-3-backend.md`

---

## Overview

Phase 3 frontend integrates the **XGBoost breakout/regression scores and SHAP explainability** from the ML backend into the existing rankings dashboard. Users see breakout/regression flags with simple explanations of *why* a player is flagged — "This player's recent xG is well below his actual goal pace (bad luck), so he's likely to regress."

**Deliverables:**
1. ✅ Fetch & cache Layer 1 trends from `/api/trends`
2. ✅ Trends column in `RankingsTable` (breakout/regression badges)
3. ✅ SHAP explainability modal (top 3 features driving the flag)
4. ✅ Mobile-friendly trend indicators
5. ✅ Zustand store slice (`trendsSlice`)
6. ✅ Test coverage (Vitest + React Testing Library)

---

## 1. Zustand Store Integration

### 1.1 New Slice: `trendsSlice`

**Location:** `apps/web/src/store/trends.ts`

```typescript
import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";

/** All 23 ESPN scoring categories — 14 raw + 9 derived. */
export interface ProjectionCategories {
  // 14 raw (from player_projections table)
  goals: number;
  assists: number;
  plus_minus: number;
  pim: number;
  ppg: number;
  ppa: number;
  shg: number;
  sha: number;
  gwg: number;
  fow: number;
  fol: number;
  shifts: number;
  hat_tricks: number;
  sog: number;
  hits: number;
  blocked_shots: number;
  // 9 derived (computed by backend from raw — never stored)
  points: number;
  pp_points: number;
  sh_points: number;
  st_goals: number;
  st_assists: number;
  st_points: number;
  defensemen_points: number;
}

export interface PlayerTrend {
  player_id: string;
  name: string;
  position: string;
  age: number;
  team: string;
  breakout_score: number;       // 0–1
  regression_risk: number;      // 0–1
  confidence: "HIGH" | "MEDIUM" | "LOW";
  projections: ProjectionCategories;
  fantasy_pts: number;          // computed from projections × user scoring_settings
  vorp: number;                 // value over replacement player (by position)
  shap_top3: Array<{
    feature: string;
    contribution: number;        // SHAP value
  }>;
}

export interface TrendsState {
  // Data
  trends: PlayerTrend[];
  selectedTrendId: string | null;

  // UI state
  isLoading: boolean;
  error: string | null;
  position_filter: "all" | "F" | "D";

  // Actions
  fetchTrends: (season: number, position?: "F" | "D") => Promise<void>;
  selectTrend: (player_id: string) => void;
  setPositionFilter: (pos: "all" | "F" | "D") => void;
  clearError: () => void;
}

export const useTrendsStore = create<TrendsState>()(
  subscribeWithSelector((set) => ({
    // Initial state
    trends: [],
    selectedTrendId: null,
    isLoading: false,
    error: null,
    position_filter: "all",

    // Actions
    fetchTrends: async (season: number, position?: "F" | "D") => {
      set({ isLoading: true, error: null });
      try {
        const params = new URLSearchParams({
          season: season.toString(),
          ...(position && { position }),
        });

        const response = await fetch(`/api/trends?${params}`);
        if (!response.ok) throw new Error("Failed to fetch trends");

        const data = await response.json();
        set({ trends: data.players, isLoading: false });
      } catch (err) {
        set({
          error: (err as Error).message,
          isLoading: false,
        });
      }
    },

    selectTrend: (player_id: string) => {
      set({ selectedTrendId: player_id });
    },

    setPositionFilter: (pos: "all" | "F" | "D") => {
      set({ position_filter: pos });
    },

    clearError: () => set({ error: null }),
  }))
);
```

---

## 2. Trends Column in Rankings Table

### 2.1 Update `RankingsTable.tsx`

**Location:** `apps/web/src/components/RankingsTable.tsx`

Add a new column after the "Rank" column:

```typescript
import { useTrendsStore, type PlayerTrend } from "@/store/trends";
import { TrendBadge } from "./TrendBadge";

export function RankingsTable() {
  const { rankings } = useRankingsStore();
  const { trends } = useTrendsStore();

  // Index trends by player_id for O(1) lookup
  const trendsMap = useMemo(
    () => new Map(trends.map((t) => [t.player_id, t])),
    [trends]
  );

  return (
    <table className="w-full">
      <thead>
        <tr>
          <th>Rank</th>
          <th>Name</th>
          <th>Pos</th>
          <th>Team</th>
          <th className="text-center">Trends</th>  {/* NEW */}
          <th className="text-right">Points</th>
          <th>Sources</th>
          {/* ... other columns */}
        </tr>
      </thead>
      <tbody>
        {rankings.map((player, idx) => {
          const trend = trendsMap.get(player.player_id);

          return (
            <tr key={player.player_id}>
              <td>{idx + 1}</td>
              <td>{player.name}</td>
              <td>{player.position}</td>
              <td>{player.team}</td>
              <td className="text-center">
                {trend ? (
                  <TrendBadge trend={trend} />
                ) : (
                  <span className="text-xs text-gray-400">—</span>
                )}
              </td>
              <td className="text-right">{player.fantasy_pts.toFixed(1)}</td>
              {/* ... other columns */}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

### 2.2 TrendBadge Component

**Location:** `apps/web/src/components/TrendBadge.tsx`

```typescript
import { useState } from "react";
import { PlayerTrend } from "@/store/trends";
import {
  TrendIcon,
  TrendModal,
} from "./TrendModal";

export function TrendBadge({ trend }: { trend: PlayerTrend }) {
  const [isOpen, setIsOpen] = useState(false);

  // Determine primary signal
  const isBreakout = trend.breakout_score > trend.regression_risk;
  const score = isBreakout ? trend.breakout_score : trend.regression_risk;
  const icon = isBreakout ? "⬆" : "⬇";
  const bgColor = isBreakout ? "bg-green-100" : "bg-red-100";
  const textColor = isBreakout ? "text-green-800" : "text-red-800";

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className={`px-2 py-1 rounded text-sm font-semibold ${bgColor} ${textColor}
                     hover:opacity-75 transition-opacity cursor-pointer`}
        title={isBreakout ? "Breakout candidate" : "Regression risk"}
      >
        <span className="mr-1">{icon}</span>
        {(score * 100).toFixed(0)}%
        <span className="ml-1 text-xs">{trend.confidence}</span>
      </button>

      {isOpen && (
        <TrendModal
          trend={trend}
          onClose={() => setIsOpen(false)}
        />
      )}
    </>
  );
}
```

---

## 3. SHAP Explainability Modal

### 3.1 TrendModal Component

**Location:** `apps/web/src/components/TrendModal.tsx`

```typescript
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { PlayerTrend } from "@/store/trends";

export function TrendModal({
  trend,
  onClose,
}: {
  trend: PlayerTrend;
  onClose: () => void;
}) {
  const isBreakout = trend.breakout_score > trend.regression_risk;
  const score = isBreakout ? trend.breakout_score : trend.regression_risk;
  const direction = isBreakout ? "breakout" : "regression";
  const icon = isBreakout ? "⬆" : "⬇";

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center gap-3">
            <div className="text-3xl">{icon}</div>
            <div>
              <h2 className="font-bold text-lg">{trend.name}</h2>
              <p className="text-sm text-gray-600">
                {trend.position} | {trend.team} | Age {trend.age}
              </p>
            </div>
          </div>

          {/* Main prediction */}
          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
            <p className="text-sm font-semibold text-blue-900">
              {direction === "breakout"
                ? `${(score * 100).toFixed(0)}% likely to BREAKOUT`
                : `${(score * 100).toFixed(0)}% risk of REGRESSION`}
            </p>
            <p className="text-xs text-blue-700 mt-1">
              Confidence: {trend.confidence}
            </p>
          </div>

          {/* Fantasy value summary */}
          <div className="grid grid-cols-2 gap-2">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-600">Projected Fantasy Points</p>
              <p className="text-xl font-bold">{trend.fantasy_pts.toFixed(1)}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-600">VORP</p>
              <p className={`text-xl font-bold ${trend.vorp >= 0 ? "text-green-700" : "text-red-700"}`}>
                {trend.vorp >= 0 ? "+" : ""}{trend.vorp.toFixed(1)}
              </p>
            </div>
          </div>

          {/* Per-category projections (key scoring stats) */}
          <ProjectionsBreakdown projections={trend.projections} position={trend.position} />

          {/* SHAP Top 3 Contributors */}
          <div>
            <h3 className="font-semibold text-sm mb-2">
              Why this {direction}?
            </h3>
            <div className="space-y-2">
              {trend.shap_top3.map((contrib, idx) => (
                <ShapContributor
                  key={idx}
                  feature={contrib.feature}
                  contribution={contrib.contribution}
                  index={idx + 1}
                />
              ))}
            </div>
          </div>

          {/* Plain-English explanation */}
          <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-200">
            <p className="text-sm text-yellow-900">
              <PlainEnglishExplanation
                trend={trend}
                direction={direction}
              />
            </p>
          </div>

          {/* Close button */}
          <button
            onClick={onClose}
            className="w-full py-2 bg-gray-200 text-gray-900 rounded font-semibold
                       hover:bg-gray-300 transition-colors"
          >
            Close
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ShapContributor({
  feature,
  contribution,
  index,
}: {
  feature: string;
  contribution: number;
  index: number;
}) {
  const isPositive = contribution > 0;
  const displayName = featureHumanReadableName(feature);

  return (
    <div className="flex items-center justify-between p-2 bg-white rounded border border-gray-200">
      <span className="text-sm">
        <span className="font-semibold">#{index}</span> {displayName}
      </span>
      <span className={isPositive ? "text-green-600" : "text-red-600"}>
        {isPositive ? "↑" : "↓"} {Math.abs(contribution).toFixed(2)}
      </span>
    </div>
  );
}

/**
 * Compact per-category projection table shown in the modal.
 * Shows the most fantasy-relevant stats; full breakdown deferred to v2.0.
 */
function ProjectionsBreakdown({
  projections,
  position,
}: {
  projections: ProjectionCategories;
  position: string;
}) {
  const rows = [
    { label: "G",     value: projections.goals },
    { label: "A",     value: projections.assists },
    { label: "PTS",   value: projections.points },
    { label: "+/-",   value: projections.plus_minus },
    { label: "PPG",   value: projections.ppg },
    { label: "PPP",   value: projections.pp_points },
    { label: "SOG",   value: projections.sog },
    { label: "GWG",   value: projections.gwg },
    ...(position === "D"
      ? [{ label: "BLK", value: projections.blocked_shots }]
      : [{ label: "HIT", value: projections.hits }]),
  ];

  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 mb-1 uppercase">
        Projected Stats
      </p>
      <div className="grid grid-cols-5 gap-1 text-center">
        {rows.map(({ label, value }) => (
          <div key={label} className="p-1 bg-gray-50 rounded text-xs">
            <p className="text-gray-500">{label}</p>
            <p className="font-bold">{value.toFixed(1)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// Human-readable feature names (SHAP → UI labels)
function featureHumanReadableName(feature: string): string {
  const names: Record<string, string> = {
    g_minus_ixg: "Goals vs Expected (Luck Gap)",
    sh_pct_delta: "Shooting % vs Career",
    pp_unit: "Power Play Unit",
    icf_per60: "Individual Shots/60 (Trend)",
    xgf_pct_5v5: "Play-Driving (xGF%)",
    pdo: "Luck Factor (PDO)",
    toi_ev_per_game: "Even-Strength Ice Time",
    age: "Age / Career Stage",
    cf_pct_adj: "Possession (Corsi %)",
    scf_per60: "Scoring Chances/60",
    elc_flag: "Entry-Level Contract Status",
    nhl_experience: "Years in NHL",
    // ... add more as needed
  };

  return names[feature] || feature;
}

// Plain-English explanation synthesized from SHAP values
function PlainEnglishExplanation({
  trend,
  direction,
}: {
  trend: PlayerTrend;
  direction: "breakout" | "regression";
}) {
  const topFeature = trend.shap_top3[0]?.feature || "unknown";

  if (direction === "breakout") {
    if (topFeature === "g_minus_ixg") {
      return "This player's goal pace is well below his expected goals (bad luck). He's likely to regress toward his xG, resulting in a breakout.";
    } else if (topFeature === "pp_unit") {
      return "He's been promoted to the power play's top unit. PP1 players see significantly higher point totals.";
    } else if (topFeature === "icf_per60") {
      return "His shot generation has been trending upward. More shots = more goals down the line.";
    }
  } else {
    // regression
    if (topFeature === "g_minus_ixg") {
      return "This player has outperformed his expected goals significantly (luck). He's likely to regress toward his xG.";
    } else if (topFeature === "sh_pct_delta") {
      return "His shooting percentage is well above his career average. Expect it to normalize downward.";
    } else if (topFeature === "pdo") {
      return "His team's on-ice luck (PDO) is unsustainably high. Regression is likely.";
    }
  }

  return `${direction === "breakout" ? "Breakout" : "Regression"} candidate based on advanced metrics.`;
}
```

---

## 4. Trends Data Fetching

### 4.1 Initialize in Dashboard Page

**Location:** `apps/web/src/app/dashboard/page.tsx`

```typescript
import { useEffect } from "react";
import { useTrendsStore } from "@/store/trends";

export default function DashboardPage() {
  const { fetchTrends, isLoading, error } = useTrendsStore();

  useEffect(() => {
    const currentSeason = new Date().getFullYear();
    fetchTrends(currentSeason);
  }, [fetchTrends]);

  return (
    <div>
      {/* Existing dashboard content */}
      {isLoading && <p>Loading trends...</p>}
      {error && <p className="text-red-600">Error: {error}</p>}

      {/* RankingsTable includes TrendBadge */}
    </div>
  );
}
```

### 4.2 Caching Strategy

Store trends in Zustand (already done by the store). Cache HTTP response with SWR:

```typescript
// Alternative: use SWR for automatic refetch
import useSWR from "swr";

export function useTrendsData(season: number) {
  const { data, error, isLoading } = useSWR(
    `/api/trends?season=${season}`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,  // 1 minute
    }
  );

  return { trends: data?.players || [], isLoading, error };
}
```

---

## 5. Mobile Responsiveness

### 5.1 TrendBadge on Mobile

Keep the badge compact on small screens:

```typescript
export function TrendBadge({ trend }: { trend: PlayerTrend }) {
  // ... existing code ...

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className={`
          px-2 py-1 rounded text-xs sm:text-sm font-semibold
          ${bgColor} ${textColor}
          hover:opacity-75 transition-opacity cursor-pointer
          whitespace-nowrap
        `}
      >
        {/* Abbreviated on mobile */}
        <span className="sm:hidden">{icon}{(score * 100).toFixed(0)}%</span>
        <span className="hidden sm:inline">
          {icon} {(score * 100).toFixed(0)}% {trend.confidence}
        </span>
      </button>

      {isOpen && (
        <TrendModal
          trend={trend}
          onClose={() => setIsOpen(false)}
        />
      )}
    </>
  );
}
```

---

## 6. Testing

### 6.1 Unit Tests

**Location:** `apps/web/src/store/__tests__/trends.test.ts`

```typescript
import { renderHook, act, waitFor } from "@testing-library/react";
import { useTrendsStore } from "@/store/trends";
import { vi } from "vitest";

describe("Trends Store", () => {
  beforeEach(() => {
    // Reset store between tests
    useTrendsStore.setState({
      trends: [],
      selectedTrendId: null,
      isLoading: false,
      error: null,
    });

    // Mock fetch
    global.fetch = vi.fn();
  });

  it("fetches trends and stores data", async () => {
    const mockData = {
      players: [
        {
          player_id: "123",
          name: "Connor McDavid",
          position: "C",
          age: 25,
          team: "EDM",
          breakout_score: 0.87,
          regression_risk: 0.12,
          confidence: "HIGH" as const,
          projections: {
            goals: 52.3, assists: 81.2, points: 133.5, plus_minus: 28.4,
            pim: 18.0, ppg: 14.1, ppa: 28.7, pp_points: 42.8,
            shg: 1.2, sha: 0.8, sh_points: 2.0, gwg: 8.1,
            fow: 812.0, fol: 704.0, shifts: 1648.0, hat_tricks: 2.1,
            sog: 312.4, hits: 42.0, blocked_shots: 18.0,
            st_goals: 15.3, st_assists: 29.5, st_points: 44.8,
            defensemen_points: 0,
          },
          fantasy_pts: 287.5,
          vorp: 142.3,
          shap_top3: [
            { feature: "g_minus_ixg", contribution: 0.45 },
            { feature: "pp_unit", contribution: 0.32 },
          ],
        },
      ],
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    } as Response);

    const { result } = renderHook(() => useTrendsStore());

    act(() => {
      result.current.fetchTrends(2026, "F");
    });

    await waitFor(() => {
      expect(result.current.trends).toHaveLength(1);
      expect(result.current.trends[0].name).toBe("Connor McDavid");
    });
  });

  it("handles fetch errors gracefully", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: async () => ({}),
    } as Response);

    const { result } = renderHook(() => useTrendsStore());

    act(() => {
      result.current.fetchTrends(2026);
    });

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("filters trends by position", async () => {
    const { result } = renderHook(() => useTrendsStore());

    act(() => {
      result.current.setPositionFilter("D");
    });

    expect(result.current.position_filter).toBe("D");
  });

  it("selects a trend for modal", async () => {
    const { result } = renderHook(() => useTrendsStore());

    act(() => {
      result.current.selectTrend("player-id-123");
    });

    expect(result.current.selectedTrendId).toBe("player-id-123");
  });
});
```

### 6.2 Component Tests

**Location:** `apps/web/src/components/__tests__/TrendBadge.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TrendBadge } from "@/components/TrendBadge";
import { PlayerTrend } from "@/store/trends";

const MOCK_PROJECTIONS = {
  goals: 52.3, assists: 81.2, points: 133.5, plus_minus: 28.4,
  pim: 18.0, ppg: 14.1, ppa: 28.7, pp_points: 42.8,
  shg: 1.2, sha: 0.8, sh_points: 2.0, gwg: 8.1,
  fow: 812.0, fol: 704.0, shifts: 1648.0, hat_tricks: 2.1,
  sog: 312.4, hits: 42.0, blocked_shots: 18.0,
  st_goals: 15.3, st_assists: 29.5, st_points: 44.8,
  defensemen_points: 0,
};

describe("TrendBadge", () => {
  const mockTrend: PlayerTrend = {
    player_id: "123",
    name: "Connor McDavid",
    position: "C",
    age: 25,
    team: "EDM",
    breakout_score: 0.87,
    regression_risk: 0.12,
    confidence: "HIGH",
    projections: MOCK_PROJECTIONS,
    fantasy_pts: 287.5,
    vorp: 142.3,
    shap_top3: [
      { feature: "g_minus_ixg", contribution: 0.45 },
      { feature: "pp_unit", contribution: 0.32 },
      { feature: "age", contribution: -0.12 },
    ],
  };

  it("renders breakout badge with correct styling", () => {
    render(<TrendBadge trend={mockTrend} />);

    const badge = screen.getByText(/87%/);
    expect(badge).toHaveClass("bg-green-100");
    expect(badge).toHaveClass("text-green-800");
  });

  it("opens modal on click", async () => {
    const user = userEvent.setup();
    render(<TrendBadge trend={mockTrend} />);

    const badge = screen.getByText(/87%/);
    await user.click(badge);

    expect(screen.getByText("Why this breakout?")).toBeInTheDocument();
  });

  it("renders regression badge with correct styling", () => {
    const regressionTrend = {
      ...mockTrend,
      breakout_score: 0.12,
      regression_risk: 0.87,
    };

    render(<TrendBadge trend={regressionTrend} />);

    const badge = screen.getByText(/87%/);
    expect(badge).toHaveClass("bg-red-100");
    expect(badge).toHaveClass("text-red-800");
  });
});
```

**Location:** `apps/web/src/components/__tests__/TrendModal.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TrendModal } from "@/components/TrendModal";
import { PlayerTrend } from "@/store/trends";

describe("TrendModal", () => {
  const mockTrend: PlayerTrend = {
    player_id: "123",
    name: "Connor McDavid",
    position: "C",
    age: 25,
    team: "EDM",
    breakout_score: 0.87,
    regression_risk: 0.12,
    confidence: "HIGH",
    projections: MOCK_PROJECTIONS,
    fantasy_pts: 287.5,
    vorp: 142.3,
    shap_top3: [
      { feature: "g_minus_ixg", contribution: 0.45 },
      { feature: "pp_unit", contribution: 0.32 },
      { feature: "age", contribution: -0.12 },
    ],
  };

  it("displays player info, prediction, and value summary", () => {
    const mockClose = vi.fn();
    render(<TrendModal trend={mockTrend} onClose={mockClose} />);

    expect(screen.getByText("Connor McDavid")).toBeInTheDocument();
    expect(screen.getByText(/87% likely to BREAKOUT/)).toBeInTheDocument();
    // Fantasy pts and VORP both rendered
    expect(screen.getByText("287.5")).toBeInTheDocument();   // fantasy_pts
    expect(screen.getByText("+142.3")).toBeInTheDocument();  // vorp
  });

  it("renders per-category projections breakdown", () => {
    const mockClose = vi.fn();
    render(<TrendModal trend={mockTrend} onClose={mockClose} />);

    expect(screen.getByText("Projected Stats")).toBeInTheDocument();
    // Spot-check a few cells
    expect(screen.getByText("G")).toBeInTheDocument();
    expect(screen.getByText("52.3")).toBeInTheDocument();
    expect(screen.getByText("PPP")).toBeInTheDocument();
    expect(screen.getByText("42.8")).toBeInTheDocument();
  });

  it("displays SHAP top 3 contributors", () => {
    const mockClose = vi.fn();
    render(<TrendModal trend={mockTrend} onClose={mockClose} />);

    expect(screen.getByText(/Goals vs Expected/)).toBeInTheDocument();
    expect(screen.getByText(/Power Play Unit/)).toBeInTheDocument();
  });

  it("closes on button click", async () => {
    const user = userEvent.setup();
    const mockClose = vi.fn();
    render(<TrendModal trend={mockTrend} onClose={mockClose} />);

    await user.click(screen.getByText("Close"));
    expect(mockClose).toHaveBeenCalled();
  });
});
```

---

## 7. Accessibility & Best Practices

### 7.1 ARIA Labels & Semantic HTML

```typescript
<button
  onClick={() => setIsOpen(true)}
  aria-label={`${trend.name} - ${trend.breakout_score > trend.regression_risk ? 'Breakout' : 'Regression'} candidate`}
  title={isBreakout ? "Breakout candidate" : "Regression risk"}
  className={...}
>
  ...
</button>
```

### 7.2 Keyboard Navigation

- Modal can be closed with `Escape` (Dialog component handles this)
- Badge is focusable via Tab
- SHAP contributors are read in order for screen readers

---

## 8. Deployment Checklist

- [ ] Trends store integrated with existing Zustand root
- [ ] RankingsTable includes TrendBadge column
- [ ] TrendModal displays on click
- [ ] SHAP top 3 contributors shown with human-readable names
- [ ] Mobile responsiveness verified
- [ ] Unit tests passing (>85% coverage)
- [ ] Vitest integration with existing test suite
- [ ] Backend `/api/trends` endpoint deployed and responding
- [ ] Error handling for API failures (fallback to "—" in table)
- [ ] Cache strategy confirmed (revalidate on dashboard load)

---

## 9. Performance Considerations

| Aspect | Target | Strategy |
|--------|--------|----------|
| Initial load (trends fetch) | <1s | SWR with cache, background revalidate |
| Modal open time | <100ms | Pre-loaded data, no additional API calls |
| Table render (850 players) | <300ms | Zustand memoization, TrendBadge is cheap |
| Mobile layout shift | <20ms | Fixed column width for trends column |

---

## 10. Future Enhancements (v2.0+)

- **Trend sparklines:** Mini chart showing breakout_score trend over last 10 years
- **Player comparison:** Side-by-side SHAP values for two players
- **Batch explainability:** Export top 50 breakout candidates with SHAP as CSV
- **In-season trends:** Layer 2 (trending_up_score) with 14-day rolling signals

---

## Appendix: Key Files

| File | Purpose |
|------|---------|
| `apps/web/src/store/trends.ts` | Zustand trends store (`PlayerTrend`, `ProjectionCategories` types) |
| `apps/web/src/components/RankingsTable.tsx` | Updated table with trends column |
| `apps/web/src/components/TrendBadge.tsx` | Badge component (clickable) |
| `apps/web/src/components/TrendModal.tsx` | Modal: SHAP explainability + per-category projections + VORP |
| `apps/web/src/app/dashboard/page.tsx` | Dashboard initialization |
| `apps/web/src/components/__tests__/TrendBadge.test.tsx` | Badge tests |
| `apps/web/src/components/__tests__/TrendModal.test.tsx` | Modal tests (projections breakdown, VORP) |
| `apps/web/src/store/__tests__/trends.test.ts` | Store tests |

---

*See also: `docs/phase-3-backend.md` (ML backend implementation)*
