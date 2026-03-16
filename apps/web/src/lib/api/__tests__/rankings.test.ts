/**
 * TDD tests for src/lib/api/rankings.ts
 * Written BEFORE the implementation — these define the expected API surface.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { computeRankings } from "@/lib/api/rankings";
import type { ProjectedStats } from "@/types";

const NULL_STATS: ProjectedStats = {
  g: null, a: null, plus_minus: null, pim: null, ppg: null, ppa: null,
  ppp: null, shg: null, sha: null, shp: null, sog: null, fow: null,
  fol: null, hits: null, blocks: null, gp: null, gs: null, w: null,
  l: null, ga: null, sa: null, sv: null, sv_pct: null, so: null, otl: null,
};

const MOCK_RESULT = {
  season: "2025-26",
  computed_at: "2026-03-06T00:00:00Z",
  cached: false,
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
      source_count: 2,
      projected_stats: NULL_STATS,
      breakout_score: null,
      regression_risk: null,
    },
  ],
};

const REQUEST = { season: "2025-26", source_weights: { nhl_com: 60, moneypuck: 40 }, scoring_config_id: "default", platform: "espn" };

beforeEach(() => {
  vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify(MOCK_RESULT), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  );
});

afterEach(() => vi.restoreAllMocks());

describe("computeRankings", () => {
  it("calls POST /rankings/compute", async () => {
    await computeRankings(REQUEST);
    const [url, init] = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/rankings/compute");
    expect(init.method).toBe("POST");
  });

  it("sends season and source_weights in the JSON body", async () => {
    await computeRankings(REQUEST);
    const [, init] = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.season).toBe("2025-26");
    expect(body.source_weights).toEqual({ nhl_com: 60, moneypuck: 40 });
  });

  it("returns the RankingsResult object", async () => {
    const result = await computeRankings(REQUEST);
    expect(result.season).toBe("2025-26");
    expect(result.cached).toBe(false);
    expect(result.rankings).toHaveLength(1);
    expect(result.rankings[0].composite_rank).toBe(1);
  });

  it("returns projected_fantasy_points on each player", async () => {
    const result = await computeRankings(REQUEST);
    expect(result.rankings[0].projected_fantasy_points).toBe(30.5);
  });

  it("includes a computed_at timestamp", async () => {
    const result = await computeRankings(REQUEST);
    expect(result.computed_at).toBeTruthy();
  });
});
