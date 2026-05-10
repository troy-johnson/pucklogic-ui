/**
 * Tests for (auth)/dashboard/page.tsx — Server Component wrapper.
 *
 * The page is an async Server Component that calls loadInitialRankings and
 * renders PreDraftWorkspace. Comprehensive interaction tests live in
 * PreDraftWorkspace.test.tsx and RankingsTable.test.tsx.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/supabase/server", () => ({
  createClient: vi.fn().mockResolvedValue({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  }),
}));

vi.mock("@/lib/rankings/load-initial", () => {
  const NULL_STATS = {
    g: null, a: null, plus_minus: null, pim: null, ppg: null, ppa: null,
    ppp: null, shg: null, sha: null, shp: null, sog: null, fow: null,
    fol: null, hits: null, blocks: null, gp: null, gs: null, w: null,
    l: null, ga: null, sa: null, sv: null, sv_pct: null, so: null, otl: null,
  };
  return {
    loadInitialRankings: vi.fn().mockResolvedValue({
      sources: [
        {
          id: "s1",
          name: "nhl_com",
          display_name: "NHL.com",
          url: null,
          active: true,
          default_weight: null,
          is_paid: false,
        },
      ],
      rankings: [
        {
          composite_rank: 1,
          player_id: "p1",
          name: "Connor McDavid",
          team: "EDM",
          default_position: "C",
          platform_positions: [],
          projected_fantasy_points: 30.5,
          vorp: null,
          schedule_score: null,
          off_night_games: null,
          source_count: 1,
          projected_stats: NULL_STATS,
          breakout_score: null,
          regression_risk: null,
        },
      ],
      loadError: false,
    }),
  };
});

vi.mock("@/store", () => ({
  useStore: vi.fn().mockReturnValue({
    sources: [],
    weights: {},
    setWeight: vi.fn(),
    resetWeights: vi.fn(),
    activeWeights: vi.fn().mockReturnValue({}),
    kits: [],
    activeKitId: null,
  }),
}));

import DashboardPage from "../page";

describe("DashboardPage (Server Component)", () => {
  it("renders the rankings table populated by loadInitialRankings", async () => {
    const element = await DashboardPage();
    render(element);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Connor McDavid")).toBeInTheDocument();
  });

  it("renders the export buttons", async () => {
    const element = await DashboardPage();
    render(element);
    expect(
      screen.getByRole("button", { name: /export rankings/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /export draft sheet/i }),
    ).toBeInTheDocument();
  });
});
