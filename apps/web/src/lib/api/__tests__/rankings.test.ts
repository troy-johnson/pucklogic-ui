/**
 * TDD tests for src/lib/api/rankings.ts
 * Written BEFORE the implementation — these define the expected API surface.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { computeRankings } from "@/lib/api/rankings";

const MOCK_RESULT = {
  season: "2025-26",
  computed_at: "2026-03-06T00:00:00Z",
  cached: false,
  rankings: [
    {
      composite_rank: 1,
      composite_score: 0.95,
      player_id: "p1",
      name: "Connor McDavid",
      team: "EDM",
      position: "C",
      source_ranks: { nhl_com: 1, moneypuck: 2 },
    },
  ],
};

const REQUEST = { season: "2025-26", weights: { nhl_com: 60, moneypuck: 40 } };

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

  it("sends season and weights in the JSON body", async () => {
    await computeRankings(REQUEST);
    const [, init] = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.season).toBe("2025-26");
    expect(body.weights).toEqual({ nhl_com: 60, moneypuck: 40 });
  });

  it("returns the RankingsResult object", async () => {
    const result = await computeRankings(REQUEST);
    expect(result.season).toBe("2025-26");
    expect(result.cached).toBe(false);
    expect(result.rankings).toHaveLength(1);
    expect(result.rankings[0].composite_rank).toBe(1);
  });

  it("preserves source_ranks on each player", async () => {
    const result = await computeRankings(REQUEST);
    expect(result.rankings[0].source_ranks).toEqual({ nhl_com: 1, moneypuck: 2 });
  });

  it("includes a computed_at timestamp", async () => {
    const result = await computeRankings(REQUEST);
    expect(result.computed_at).toBeTruthy();
  });
});
