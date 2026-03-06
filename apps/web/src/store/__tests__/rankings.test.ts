/**
 * TDD tests for src/store/slices/rankings.ts
 *
 * Each test creates a fresh isolated store.
 * Written BEFORE the implementation — these drive the slice design.
 */
import { create } from "zustand";
import { beforeEach, describe, expect, it } from "vitest";

import { createRankingsSlice, type RankingsSlice } from "@/store/slices/rankings";
import type { RankingsResult } from "@/types";

function makeStore() {
  return create<RankingsSlice>()((...a) => ({ ...createRankingsSlice(...a) }));
}

const RESULT: RankingsResult = {
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
      source_ranks: { nhl_com: 1 },
    },
  ],
};

describe("RankingsSlice — initial state", () => {
  it("has the current NHL season as default season", () => {
    expect(makeStore().getState().season).toBe("2025-26");
  });

  it("starts with an empty rankings array", () => {
    expect(makeStore().getState().rankings).toEqual([]);
  });

  it("starts with loading=false", () => {
    expect(makeStore().getState().loading).toBe(false);
  });

  it("starts with error=null", () => {
    expect(makeStore().getState().error).toBeNull();
  });

  it("starts with cached=false", () => {
    expect(makeStore().getState().cached).toBe(false);
  });

  it("starts with computedAt=null", () => {
    expect(makeStore().getState().computedAt).toBeNull();
  });
});

describe("setSeason", () => {
  it("updates the season", () => {
    const store = makeStore();
    store.getState().setSeason("2026-27");
    expect(store.getState().season).toBe("2026-27");
  });

  it("clears existing rankings when season changes", () => {
    const store = makeStore();
    store.getState().setRankings(RESULT);
    store.getState().setSeason("2026-27");
    expect(store.getState().rankings).toEqual([]);
  });

  it("clears error when season changes", () => {
    const store = makeStore();
    store.getState().setError("Something went wrong");
    store.getState().setSeason("2026-27");
    expect(store.getState().error).toBeNull();
  });
});

describe("setRankings", () => {
  let store: ReturnType<typeof makeStore>;
  beforeEach(() => { store = makeStore(); });

  it("stores the rankings array", () => {
    store.getState().setRankings(RESULT);
    expect(store.getState().rankings).toHaveLength(1);
    expect(store.getState().rankings[0].player_id).toBe("p1");
  });

  it("stores cached flag", () => {
    store.getState().setRankings({ ...RESULT, cached: true });
    expect(store.getState().cached).toBe(true);
  });

  it("stores computed_at as computedAt", () => {
    store.getState().setRankings(RESULT);
    expect(store.getState().computedAt).toBe("2026-03-06T00:00:00Z");
  });

  it("clears any previous error", () => {
    store.getState().setError("previous error");
    store.getState().setRankings(RESULT);
    expect(store.getState().error).toBeNull();
  });

  it("sets loading to false", () => {
    store.getState().setLoading(true);
    store.getState().setRankings(RESULT);
    expect(store.getState().loading).toBe(false);
  });
});

describe("setLoading", () => {
  it("sets loading true", () => {
    const store = makeStore();
    store.getState().setLoading(true);
    expect(store.getState().loading).toBe(true);
  });

  it("sets loading false", () => {
    const store = makeStore();
    store.getState().setLoading(true);
    store.getState().setLoading(false);
    expect(store.getState().loading).toBe(false);
  });
});

describe("setError", () => {
  it("stores the error message", () => {
    const store = makeStore();
    store.getState().setError("Network error");
    expect(store.getState().error).toBe("Network error");
  });

  it("sets loading to false when error is set", () => {
    const store = makeStore();
    store.getState().setLoading(true);
    store.getState().setError("Network error");
    expect(store.getState().loading).toBe(false);
  });

  it("clears the error when null is passed", () => {
    const store = makeStore();
    store.getState().setError("oops");
    store.getState().setError(null);
    expect(store.getState().error).toBeNull();
  });
});

describe("clearRankings", () => {
  it("empties the rankings array", () => {
    const store = makeStore();
    store.getState().setRankings(RESULT);
    store.getState().clearRankings();
    expect(store.getState().rankings).toEqual([]);
  });

  it("resets cached to false", () => {
    const store = makeStore();
    store.getState().setRankings({ ...RESULT, cached: true });
    store.getState().clearRankings();
    expect(store.getState().cached).toBe(false);
  });

  it("resets computedAt to null", () => {
    const store = makeStore();
    store.getState().setRankings(RESULT);
    store.getState().clearRankings();
    expect(store.getState().computedAt).toBeNull();
  });
});
