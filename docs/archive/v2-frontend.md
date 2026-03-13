# PuckLogic v2.0 — Frontend Implementation

## In-Season Trends Panel (Layer 2 UI)

**Timeline:** Post-launch (after v1.0 September 2026 release)
**Target Release:** v2.0 (TBD — in-season 2026–27)
**Backend Reference:** `docs/v2-backend.md`

---

## Overview

v2.0 frontend extends the Phase 3 Trends UI with the **Layer 2 in-season leading indicator panel**. Users see a live momentum score, per-signal Z-score breakdown, and a combined `pucklogic_trends_score` that blends the pre-season Layer 1 breakout model with the in-season Layer 2 signal engine.

The UI is subscription-aware: free-tier users see the top-10 trending players blurred with a paywall overlay and an upgrade CTA. Pro users see the full `signals_json` explainability breakdown for every player.

SWR polling refreshes trend data every 60 seconds during the in-season window (Oct–Apr) and is disabled entirely in the pre-season to avoid unnecessary requests.

**Deliverables (all planned — v2.0 is post-launch):**
1. ☐ Layer 2 signals breakdown panel in `TrendModal` (replaces "Phase 3 only" view in-season)
2. ☐ `MomentumBadge` component — directional arrow with 0–100 score
3. ☐ `SignalsBreakdown` component — per-signal Z-score table with color coding
4. ☐ Combined `pucklogic_trends_score` display (replaces separate Layer 1 / Layer 2 scores in-season view)
5. ☐ `PaywallOverlay` component — blur + upgrade CTA for top-10 free-tier players
6. ☐ Real-time score updates via SWR polling (60s interval, in-season only)
7. ☐ In-season vs. pre-season context switching in `TrendModal`
8. ☐ Test coverage (Vitest + React Testing Library)

---

## 1. Updated Store Types

### 1.1 Layer 2 Type Extensions

**Location:** `apps/web/src/store/trends.ts`

The following types are added to the existing Phase 3 store file. All Phase 3 types (`ProjectionCategories`, `TrendsState`, `useTrendsStore`, etc.) remain unchanged.

```typescript
/** Layer 2 per-signal Z-scores, stored in signals_json on the backend.
 *  null for free-tier users on the top-10 paywalled players.
 */
export interface Layer2Signals {
  toi_change:              number;   // Z-score: TOI delta (5v5, PP, SH)
  pp_unit_movement:        number;   // Z-score: PP1 ↔ PP2 transition
  shots_trend:             number;   // Z-score: shots/game trend
  xgf_shift:               number;   // Z-score: xGF% delta
  corsi_shift:             number;   // Z-score: Corsi rel% delta
  line_combo_change:       number;   // Z-score: line position change
  shooting_pct_regression: number;   // Z-score: sh% vs career mean
}

/** Human-readable labels for each Layer 2 signal key. */
export const SIGNAL_LABELS: Record<keyof Layer2Signals, string> = {
  toi_change:              "Ice Time Change",
  pp_unit_movement:        "PP Unit Movement",
  shots_trend:             "Shots / Game Trend",
  xgf_shift:               "Expected Goals % Shift",
  corsi_shift:             "Corsi Rel% Shift",
  line_combo_change:       "Line Combo Change",
  shooting_pct_regression: "Shooting % vs Career",
};

/** Extended PlayerTrend with v2.0 Layer 2 fields.
 *  Extends the Phase 3 PlayerTrend interface.
 */
export interface PlayerTrend {
  // Phase 3 fields (unchanged)
  player_id:       string;
  name:            string;
  position:        string;
  age:             number;
  team:            string;
  breakout_score:  number;                          // 0–1
  regression_risk: number;                          // 0–1
  confidence:      "HIGH" | "MEDIUM" | "LOW";
  projections:     ProjectionCategories;
  fantasy_pts:     number;
  vorp:            number;
  shap_top3:       Array<{ feature: string; contribution: number }>;

  // v2.0 Layer 2 additions
  trending_up_score:        number | null;  // 0–100; null before v2.0 launch
  trending_down_score:      number | null;  // 0–100
  momentum_score:           number | null;  // 0–100, centered at 50
  signals_json:             Layer2Signals | null;  // null for paywalled free-tier top-10
  window_days:              number;                // always 14
  pucklogic_trends_score:   number | null;  // blended 0–100

  // Paywall flag — set by backend for free-tier top-10
  paywalled: boolean;
}
```

### 1.2 Season Phase Helper

**Location:** `apps/web/src/lib/season.ts`

```typescript
/** Returns true when today falls in the in-season window (Oct–Apr). */
export function isInSeason(date: Date = new Date()): boolean {
  const month = date.getMonth() + 1;   // getMonth() is 0-indexed
  return month >= 10 || month <= 4;
}

/** Returns a label describing the current blending weights for display. */
export function getTrendsWeightLabel(date: Date = new Date()): string {
  return isInSeason(date)
    ? "In-season blend (30% pre-season / 70% in-season)"
    : "Pre-season blend (80% pre-season / 20% in-season)";
}
```

---

## 2. SWR Polling (In-season Only)

### 2.1 Updated `useTrends` Hook

**Location:** `apps/web/src/lib/api/trends.ts`

```typescript
import useSWR from "swr";
import { isInSeason } from "@/lib/season";

const fetcher = (url: string) =>
  fetch(url).then((res) => {
    if (!res.ok) throw new Error("Failed to fetch trends");
    return res.json();
  });

/** Fetches Layer 1 + Layer 2 trends for the given season.
 *
 *  Polling behaviour:
 *    - In-season (Oct–Apr): refreshes every 60 seconds and on window focus.
 *    - Pre-season (Aug–Sep): no polling; data changes only after retraining.
 */
export function useTrends(season: string) {
  const inSeason = isInSeason(new Date());

  return useSWR(
    `/api/trends?season=${season}`,
    fetcher,
    {
      refreshInterval:  inSeason ? 60_000 : 0,   // 60s in-season, never pre-season
      revalidateOnFocus: inSeason,
      dedupingInterval: 30_000,
    }
  );
}
```

---

## 3. `MomentumBadge` Component

### 3.1 Component

**Location:** `apps/web/src/components/trends/MomentumBadge.tsx`

Displays a directional arrow and 0–100 score. Score is centered at 50: above 55 is trending up, below 45 is trending down, 45–55 is stable.

```typescript
interface MomentumBadgeProps {
  score: number;          // 0–100, centered at 50
  size?: "sm" | "md";
}

type Direction = "up" | "down" | "stable";

function getDirection(score: number): Direction {
  if (score > 55) return "up";
  if (score < 45) return "down";
  return "stable";
}

const DIRECTION_STYLES: Record<Direction, { color: string; icon: string; label: string }> = {
  up:     { color: "text-green-500", icon: "↑", label: "Trending up" },
  down:   { color: "text-red-500",   icon: "↓", label: "Trending down" },
  stable: { color: "text-gray-400",  icon: "→", label: "Stable" },
};

export function MomentumBadge({ score, size = "md" }: MomentumBadgeProps) {
  const direction = getDirection(score);
  const { color, icon, label } = DIRECTION_STYLES[direction];
  const textSize = size === "sm" ? "text-xs" : "text-sm";

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono ${color} ${textSize}`}
      aria-label={`Momentum: ${label} (${score.toFixed(0)}/100)`}
      title={label}
    >
      <span aria-hidden="true">{icon}</span>
      <span>{score.toFixed(0)}/100</span>
    </span>
  );
}
```

---

## 4. `SignalsBreakdown` Component

### 4.1 Component

**Location:** `apps/web/src/components/trends/SignalsBreakdown.tsx`

Renders a table of per-signal Z-scores when `signals_json` is available. Renders blurred placeholder rows with a lock icon when the player is paywalled.

```typescript
import { Layer2Signals, SIGNAL_LABELS } from "@/store/trends";
import { LockClosedIcon } from "@heroicons/react/24/solid";

interface SignalsBreakdownProps {
  signals: Layer2Signals | null;   // null → paywalled
  paywalled: boolean;
  windowDays: number;              // always 14 for now
}

function zScoreColor(z: number): string {
  if (z > 0.5)  return "text-green-600";
  if (z < -0.5) return "text-red-600";
  return "text-gray-500";
}

function zScoreArrow(z: number): string {
  if (z > 0.5)  return "↑";
  if (z < -0.5) return "↓";
  return "→";
}

export function SignalsBreakdown({ signals, paywalled, windowDays }: SignalsBreakdownProps) {
  const signalKeys = Object.keys(SIGNAL_LABELS) as Array<keyof Layer2Signals>;

  return (
    <div className="relative">
      <p className="text-xs font-semibold text-gray-500 mb-2 uppercase">
        {windowDays}-Day Leading Signals
      </p>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-gray-400 border-b border-gray-100">
            <th className="text-left py-1 font-medium">Signal</th>
            <th className="text-right py-1 font-medium">Z-Score</th>
            <th className="text-right py-1 font-medium">Direction</th>
          </tr>
        </thead>
        <tbody>
          {signalKeys.map((key) => {
            const z = signals?.[key] ?? 0;
            const isBlurred = paywalled;

            return (
              <tr
                key={key}
                className={`border-b border-gray-50 ${isBlurred ? "blur-sm select-none" : ""}`}
                aria-hidden={isBlurred}
              >
                <td className="py-1.5 text-gray-700">{SIGNAL_LABELS[key]}</td>
                <td className={`py-1.5 text-right font-mono ${isBlurred ? "" : zScoreColor(z)}`}>
                  {isBlurred ? "–.––" : z.toFixed(2)}
                </td>
                <td className={`py-1.5 text-right ${isBlurred ? "" : zScoreColor(z)}`}>
                  {isBlurred ? "–" : zScoreArrow(z)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {paywalled && (
        <div className="absolute inset-0 flex items-center justify-center">
          <LockClosedIcon className="h-5 w-5 text-muted-foreground opacity-60" />
        </div>
      )}
    </div>
  );
}
```

---

## 5. `PaywallOverlay` Component

### 5.1 Component

**Location:** `apps/web/src/components/trends/PaywallOverlay.tsx`

Rendered over `TrendModal` content when `player.paywalled === true`. The parent wrapper must be `position: relative` for the overlay to fill it correctly.

```typescript
import { LockClosedIcon } from "@heroicons/react/24/solid";
import { Button } from "@/components/ui/button";

export function PaywallOverlay() {
  return (
    <div
      className="absolute inset-0 flex flex-col items-center justify-center
                 bg-background/80 backdrop-blur-sm rounded-lg z-10"
      role="region"
      aria-label="Pro feature — upgrade required"
    >
      <LockClosedIcon className="h-8 w-8 text-muted-foreground mb-2" />
      <p className="text-sm font-medium text-center px-4">
        Top trending players require Pro
      </p>
      <p className="text-xs text-muted-foreground text-center px-6 mt-1">
        Unlock full signal breakdowns for all players
      </p>
      <Button variant="default" size="sm" className="mt-4" asChild>
        <a href="/dashboard/settings/billing">Upgrade to Pro</a>
      </Button>
    </div>
  );
}
```

---

## 6. Updated `TrendModal` (v2.0 View)

### 6.1 Season-Aware Modal

**Location:** `apps/web/src/components/trends/TrendModal.tsx`

The modal shows different content depending on the current season phase. The Phase 3 pre-season view (breakout_score, SHAP features, per-category projections) is retained in full; the in-season view adds the Layer 2 panel beneath it.

```typescript
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { PlayerTrend } from "@/store/trends";
import { MomentumBadge } from "./MomentumBadge";
import { SignalsBreakdown } from "./SignalsBreakdown";
import { PaywallOverlay } from "./PaywallOverlay";
import { isInSeason, getTrendsWeightLabel } from "@/lib/season";

export function TrendModal({
  trend,
  onClose,
}: {
  trend: PlayerTrend;
  onClose: () => void;
}) {
  const inSeason = isInSeason(new Date());
  const isBreakout = trend.breakout_score > trend.regression_risk;

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        {/* Relative wrapper required for PaywallOverlay to position correctly */}
        <div className="relative space-y-4">
          {trend.paywalled && <PaywallOverlay />}

          {/* Player header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-bold text-lg">{trend.name}</h2>
              <p className="text-sm text-gray-600">
                {trend.position} | {trend.team} | Age {trend.age}
              </p>
            </div>
            {/* Combined score (in-season) or breakout score (pre-season) */}
            {inSeason && trend.pucklogic_trends_score !== null ? (
              <div className="text-right">
                <p className="text-xs text-gray-500 mb-0.5">PuckLogic Score</p>
                <p className="text-2xl font-bold">
                  {trend.pucklogic_trends_score.toFixed(0)}
                  <span className="text-sm text-gray-400">/100</span>
                </p>
                {trend.momentum_score !== null && (
                  <MomentumBadge score={trend.momentum_score} size="sm" />
                )}
              </div>
            ) : (
              <div className="text-right">
                <p className="text-xs text-gray-500 mb-0.5">
                  {isBreakout ? "Breakout" : "Regression Risk"}
                </p>
                <p className="text-2xl font-bold">
                  {((isBreakout ? trend.breakout_score : trend.regression_risk) * 100).toFixed(0)}%
                </p>
              </div>
            )}
          </div>

          {/* Blending weight context label */}
          <p className="text-xs text-muted-foreground">
            {getTrendsWeightLabel(new Date())}
          </p>

          {/* Fantasy value summary (both views) */}
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

          {/* Per-category projections (both views) */}
          <ProjectionsBreakdown projections={trend.projections} position={trend.position} />

          {/* In-season view: Layer 2 signals panel */}
          {inSeason && (
            <SignalsBreakdown
              signals={trend.signals_json}
              paywalled={trend.paywalled}
              windowDays={trend.window_days}
            />
          )}

          {/* Pre-season view: SHAP explainability (Phase 3 — unchanged) */}
          {!inSeason && (
            <div>
              <h3 className="font-semibold text-sm mb-2">
                Why this {isBreakout ? "breakout" : "regression"}?
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
          )}

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
```

---

## 7. `TrendBadge` — In-season Update

### 7.1 Combined Score in Badge

**Location:** `apps/web/src/components/trends/TrendBadge.tsx`

The existing Phase 3 `TrendBadge` is updated to show `pucklogic_trends_score` during the in-season window alongside the `MomentumBadge`, while retaining the Phase 3 breakout/regression display for pre-season.

```typescript
import { isInSeason } from "@/lib/season";
import { MomentumBadge } from "./MomentumBadge";
import { PlayerTrend } from "@/store/trends";

export function TrendBadge({ trend }: { trend: PlayerTrend }) {
  const [isOpen, setIsOpen] = useState(false);
  const inSeason = isInSeason(new Date());

  // In-season: show combined score + momentum direction
  if (inSeason && trend.pucklogic_trends_score !== null && trend.momentum_score !== null) {
    return (
      <>
        <button
          onClick={() => setIsOpen(true)}
          className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-blue-50 text-blue-800
                     hover:opacity-75 transition-opacity cursor-pointer text-xs font-semibold"
          aria-label={`${trend.name} — PuckLogic Trends Score ${trend.pucklogic_trends_score.toFixed(0)}/100`}
        >
          <span className="font-mono">{trend.pucklogic_trends_score.toFixed(0)}</span>
          <MomentumBadge score={trend.momentum_score} size="sm" />
        </button>
        {isOpen && <TrendModal trend={trend} onClose={() => setIsOpen(false)} />}
      </>
    );
  }

  // Pre-season: existing Phase 3 badge (breakout/regression)
  const isBreakout = trend.breakout_score > trend.regression_risk;
  const score = isBreakout ? trend.breakout_score : trend.regression_risk;
  const icon = isBreakout ? "⬆" : "⬇";
  const bgColor = isBreakout ? "bg-green-100" : "bg-red-100";
  const textColor = isBreakout ? "text-green-800" : "text-red-800";

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className={`px-2 py-1 rounded text-xs sm:text-sm font-semibold
                     ${bgColor} ${textColor}
                     hover:opacity-75 transition-opacity cursor-pointer whitespace-nowrap`}
        aria-label={`${trend.name} — ${isBreakout ? "Breakout candidate" : "Regression risk"} ${(score * 100).toFixed(0)}%`}
        title={isBreakout ? "Breakout candidate" : "Regression risk"}
      >
        <span className="sm:hidden">{icon}{(score * 100).toFixed(0)}%</span>
        <span className="hidden sm:inline">
          {icon} {(score * 100).toFixed(0)}% {trend.confidence}
        </span>
      </button>
      {isOpen && <TrendModal trend={trend} onClose={() => setIsOpen(false)} />}
    </>
  );
}
```

---

## 8. Testing

### 8.1 `MomentumBadge` Tests

**Location:** `apps/web/src/components/trends/__tests__/MomentumBadge.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import { MomentumBadge } from "@/components/trends/MomentumBadge";

describe("MomentumBadge", () => {
  it("renders green up arrow when score > 55", () => {
    render(<MomentumBadge score={70} />);
    const badge = screen.getByText("70/100");
    expect(badge.closest("span")).toHaveClass("text-green-500");
    expect(screen.getByText("↑")).toBeInTheDocument();
  });

  it("renders red down arrow when score < 45", () => {
    render(<MomentumBadge score={30} />);
    const badge = screen.getByText("30/100");
    expect(badge.closest("span")).toHaveClass("text-red-500");
    expect(screen.getByText("↓")).toBeInTheDocument();
  });

  it("renders gray stable arrow when score is 45–55", () => {
    render(<MomentumBadge score={50} />);
    const badge = screen.getByText("50/100");
    expect(badge.closest("span")).toHaveClass("text-gray-400");
    expect(screen.getByText("→")).toBeInTheDocument();
  });

  it("applies correct aria-label", () => {
    render(<MomentumBadge score={70} />);
    expect(screen.getByLabelText(/Momentum: Trending up/i)).toBeInTheDocument();
  });

  it("applies sm text size when size='sm'", () => {
    render(<MomentumBadge score={60} size="sm" />);
    expect(screen.getByText("60/100").closest("span")).toHaveClass("text-xs");
  });
});
```

### 8.2 `SignalsBreakdown` Tests

**Location:** `apps/web/src/components/trends/__tests__/SignalsBreakdown.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import { SignalsBreakdown } from "@/components/trends/SignalsBreakdown";
import { Layer2Signals } from "@/store/trends";

const MOCK_SIGNALS: Layer2Signals = {
  toi_change:              1.4,
  pp_unit_movement:        2.1,
  shots_trend:             0.8,
  xgf_shift:              -0.3,
  corsi_shift:            -0.7,
  line_combo_change:       0.2,
  shooting_pct_regression: -1.2,
};

describe("SignalsBreakdown", () => {
  it("renders all 7 signal rows", () => {
    render(
      <SignalsBreakdown signals={MOCK_SIGNALS} paywalled={false} windowDays={14} />
    );
    expect(screen.getByText("Ice Time Change")).toBeInTheDocument();
    expect(screen.getByText("PP Unit Movement")).toBeInTheDocument();
    expect(screen.getByText("Shots / Game Trend")).toBeInTheDocument();
    expect(screen.getByText("Expected Goals % Shift")).toBeInTheDocument();
    expect(screen.getByText("Corsi Rel% Shift")).toBeInTheDocument();
    expect(screen.getByText("Line Combo Change")).toBeInTheDocument();
    expect(screen.getByText("Shooting % vs Career")).toBeInTheDocument();
  });

  it("shows formatted Z-scores for non-paywalled players", () => {
    render(
      <SignalsBreakdown signals={MOCK_SIGNALS} paywalled={false} windowDays={14} />
    );
    expect(screen.getByText("1.40")).toBeInTheDocument();
    expect(screen.getByText("2.10")).toBeInTheDocument();
  });

  it("blurs rows for paywalled players", () => {
    render(
      <SignalsBreakdown signals={null} paywalled={true} windowDays={14} />
    );
    // Paywalled rows have blur-sm class
    const rows = document.querySelectorAll("tr.blur-sm");
    expect(rows.length).toBe(7);
  });

  it("renders lock icon when paywalled", () => {
    render(
      <SignalsBreakdown signals={null} paywalled={true} windowDays={14} />
    );
    // LockClosedIcon is rendered — check by aria or SVG presence
    expect(document.querySelector("svg")).toBeInTheDocument();
  });

  it("shows the rolling window label", () => {
    render(
      <SignalsBreakdown signals={MOCK_SIGNALS} paywalled={false} windowDays={14} />
    );
    expect(screen.getByText(/14-Day Leading Signals/i)).toBeInTheDocument();
  });
});
```

### 8.3 `PaywallOverlay` Tests

**Location:** `apps/web/src/components/trends/__tests__/PaywallOverlay.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import { PaywallOverlay } from "@/components/trends/PaywallOverlay";

describe("PaywallOverlay", () => {
  it("renders upgrade CTA with correct billing link", () => {
    render(<PaywallOverlay />);
    const link = screen.getByRole("link", { name: /upgrade to pro/i });
    expect(link).toHaveAttribute("href", "/dashboard/settings/billing");
  });

  it("renders lock icon", () => {
    render(<PaywallOverlay />);
    expect(document.querySelector("svg")).toBeInTheDocument();
  });

  it("renders descriptive copy", () => {
    render(<PaywallOverlay />);
    expect(screen.getByText(/Top trending players require Pro/i)).toBeInTheDocument();
  });

  it("has correct aria region label", () => {
    render(<PaywallOverlay />);
    expect(screen.getByRole("region", { name: /upgrade required/i })).toBeInTheDocument();
  });
});
```

### 8.4 `TrendModal` v2.0 Tests

**Location:** `apps/web/src/components/trends/__tests__/TrendModal.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { TrendModal } from "@/components/trends/TrendModal";
import { PlayerTrend } from "@/store/trends";
import * as seasonLib from "@/lib/season";

const BASE_TREND: PlayerTrend = {
  player_id: "123",
  name: "Connor McDavid",
  position: "C",
  age: 25,
  team: "EDM",
  breakout_score: 0.87,
  regression_risk: 0.12,
  confidence: "HIGH",
  projections: { /* ... */ } as any,
  fantasy_pts: 287.5,
  vorp: 142.3,
  shap_top3: [{ feature: "g_minus_ixg", contribution: 0.45 }],
  // v2.0 fields
  trending_up_score: 78,
  trending_down_score: 22,
  momentum_score: 68,
  signals_json: {
    toi_change: 1.4, pp_unit_movement: 2.1, shots_trend: 0.8,
    xgf_shift: -0.3, corsi_shift: -0.7, line_combo_change: 0.2,
    shooting_pct_regression: -1.2,
  },
  window_days: 14,
  pucklogic_trends_score: 74,
  paywalled: false,
};

describe("TrendModal — pre-season view", () => {
  beforeEach(() => {
    vi.spyOn(seasonLib, "isInSeason").mockReturnValue(false);
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows breakout_score — not momentum or combined score", () => {
    render(<TrendModal trend={BASE_TREND} onClose={vi.fn()} />);
    expect(screen.getByText(/87%/)).toBeInTheDocument();
    expect(screen.queryByText(/74\/100/)).not.toBeInTheDocument();
  });

  it("renders SHAP top contributors", () => {
    render(<TrendModal trend={BASE_TREND} onClose={vi.fn()} />);
    expect(screen.getByText(/Goals vs Expected/)).toBeInTheDocument();
  });

  it("does not render SignalsBreakdown", () => {
    render(<TrendModal trend={BASE_TREND} onClose={vi.fn()} />);
    expect(screen.queryByText(/14-Day Leading Signals/i)).not.toBeInTheDocument();
  });
});

describe("TrendModal — in-season view", () => {
  beforeEach(() => {
    vi.spyOn(seasonLib, "isInSeason").mockReturnValue(true);
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows pucklogic_trends_score and MomentumBadge", () => {
    render(<TrendModal trend={BASE_TREND} onClose={vi.fn()} />);
    expect(screen.getByText("74")).toBeInTheDocument();   // combined score
    expect(screen.getByText("68/100")).toBeInTheDocument(); // momentum badge
  });

  it("does not show standalone breakout_score percentage", () => {
    render(<TrendModal trend={BASE_TREND} onClose={vi.fn()} />);
    expect(screen.queryByText(/87%/)).not.toBeInTheDocument();
  });

  it("renders SignalsBreakdown table", () => {
    render(<TrendModal trend={BASE_TREND} onClose={vi.fn()} />);
    expect(screen.getByText(/14-Day Leading Signals/i)).toBeInTheDocument();
  });

  it("renders PaywallOverlay when paywalled=true", () => {
    const paywalled = { ...BASE_TREND, paywalled: true, signals_json: null };
    render(<TrendModal trend={paywalled} onClose={vi.fn()} />);
    expect(screen.getByText(/Top trending players require Pro/i)).toBeInTheDocument();
  });

  it("does not render PaywallOverlay when paywalled=false", () => {
    render(<TrendModal trend={BASE_TREND} onClose={vi.fn()} />);
    expect(screen.queryByText(/Top trending players require Pro/i)).not.toBeInTheDocument();
  });

  it("closes on button click", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<TrendModal trend={BASE_TREND} onClose={onClose} />);
    await user.click(screen.getByText("Close"));
    expect(onClose).toHaveBeenCalled();
  });
});
```

---

## 9. Accessibility & Best Practices

| Concern | Implementation |
|---------|---------------|
| `MomentumBadge` aria | `aria-label` includes score and direction (e.g., "Momentum: Trending up (68/100)") |
| `SignalsBreakdown` paywalled rows | `aria-hidden="true"` on blurred rows — screen readers skip them |
| `PaywallOverlay` | `role="region"` with descriptive `aria-label` |
| `TrendModal` keyboard nav | `Dialog` from shadcn/ui handles `Escape` to close and focus trap |
| `TrendBadge` aria | `aria-label` includes player name and score type |
| Color-only indicators | Z-score arrows (↑ / ↓ / →) accompany all color coding — not color alone |

---

## 10. Performance Considerations

| Aspect | Target | Strategy |
|--------|--------|----------|
| Initial trends fetch | < 1s | SWR with 30s dedup, cached at CDN edge |
| In-season polling | 60s interval | SWR `refreshInterval`; no polling pre-season |
| Modal open time | < 100ms | All data pre-loaded — no additional API calls on click |
| `SignalsBreakdown` render | < 16ms | 7-row table, no async work |
| Paywall check | Synchronous | `player.paywalled` flag set by backend — no client-side subscription check needed |

---

## 11. Deployment Checklist

- [ ] `Layer2Signals` and updated `PlayerTrend` types exported from `apps/web/src/store/trends.ts`
- [ ] `isInSeason()` helper live in `apps/web/src/lib/season.ts`
- [ ] `useTrends()` hook polling confirmed at 60s in-season, 0 pre-season
- [ ] `MomentumBadge` renders correctly for all three direction states
- [ ] `SignalsBreakdown` blurs rows and shows lock icon when `paywalled=true`
- [ ] `PaywallOverlay` links to `/dashboard/settings/billing`
- [ ] `TrendModal` pre-season view unchanged from Phase 3
- [ ] `TrendModal` in-season view renders combined score, MomentumBadge, and SignalsBreakdown
- [ ] `TrendBadge` shows combined score in-season, breakout/regression pre-season
- [ ] All Vitest tests green
- [ ] Backend `/api/trends` endpoint confirmed returning `signals_json` and `paywalled` fields
- [ ] Stripe billing page live at `/dashboard/settings/billing` for paywall CTA target

---

## Appendix: Key Files

| File | Purpose |
|------|---------|
| `apps/web/src/store/trends.ts` | Updated types: `Layer2Signals`, `SIGNAL_LABELS`, extended `PlayerTrend` |
| `apps/web/src/lib/season.ts` | `isInSeason()`, `getTrendsWeightLabel()` helpers |
| `apps/web/src/lib/api/trends.ts` | `useTrends()` SWR hook with in-season polling |
| `apps/web/src/components/trends/TrendModal.tsx` | Updated modal with pre-season / in-season switching |
| `apps/web/src/components/trends/MomentumBadge.tsx` | Directional momentum score indicator |
| `apps/web/src/components/trends/SignalsBreakdown.tsx` | Per-signal Z-score table with paywall blur |
| `apps/web/src/components/trends/PaywallOverlay.tsx` | Blur overlay + upgrade CTA |
| `apps/web/src/components/trends/TrendBadge.tsx` | Updated badge (combined score in-season) |
| `apps/web/src/components/trends/__tests__/MomentumBadge.test.tsx` | Badge direction + color tests |
| `apps/web/src/components/trends/__tests__/SignalsBreakdown.test.tsx` | Signal rows + paywall blur tests |
| `apps/web/src/components/trends/__tests__/TrendModal.test.tsx` | Pre-season / in-season / paywall modal tests |
| `apps/web/src/components/trends/__tests__/PaywallOverlay.test.tsx` | Overlay CTA and aria tests |

---

*See also: `docs/v2-backend.md` (Layer 2 Z-score engine, Celery job, subscription gate API) · `docs/phase-3-frontend.md` (Phase 3 Layer 1 UI — retained in full)*
