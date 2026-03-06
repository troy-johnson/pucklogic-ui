/**
 * TDD tests for src/store/slices/sources.ts
 *
 * Each test creates a fresh isolated store so state never leaks between tests.
 * Written BEFORE the implementation — these drive the slice design.
 */
import { create } from "zustand";
import { beforeEach, describe, expect, it } from "vitest";

import { createSourcesSlice, type SourcesSlice } from "@/store/slices/sources";
import type { Source } from "@/types";

const NHL: Source = { id: "s1", name: "nhl_com", display_name: "NHL.com", url: null, active: true };
const MP: Source = { id: "s2", name: "moneypuck", display_name: "MoneyPuck", url: null, active: true };

function makeStore() {
  return create<SourcesSlice>()((...a) => ({ ...createSourcesSlice(...a) }));
}

describe("SourcesSlice — initial state", () => {
  it("starts with an empty sources array", () => {
    expect(makeStore().getState().sources).toEqual([]);
  });

  it("starts with empty weights", () => {
    expect(makeStore().getState().weights).toEqual({});
  });
});

describe("setSources", () => {
  let store: ReturnType<typeof makeStore>;
  beforeEach(() => { store = makeStore(); });

  it("stores the provided sources", () => {
    store.getState().setSources([NHL, MP]);
    expect(store.getState().sources).toHaveLength(2);
  });

  it("initialises equal weights for all sources", () => {
    store.getState().setSources([NHL, MP]);
    const w = store.getState().weights;
    expect(w["nhl_com"]).toBe(50);
    expect(w["moneypuck"]).toBe(50);
  });

  it("initialises weight of 100 when only one source", () => {
    store.getState().setSources([NHL]);
    expect(store.getState().weights["nhl_com"]).toBe(100);
  });

  it("replaces previous sources", () => {
    store.getState().setSources([NHL]);
    store.getState().setSources([MP]);
    expect(store.getState().sources).toHaveLength(1);
    expect(store.getState().sources[0].name).toBe("moneypuck");
  });

  it("does nothing to weights when sources list is empty", () => {
    store.getState().setSources([]);
    expect(store.getState().weights).toEqual({});
  });
});

describe("setWeight", () => {
  let store: ReturnType<typeof makeStore>;
  beforeEach(() => {
    store = makeStore();
    store.getState().setSources([NHL, MP]);
  });

  it("updates the weight for the given source", () => {
    store.getState().setWeight("nhl_com", 75);
    expect(store.getState().weights["nhl_com"]).toBe(75);
  });

  it("leaves other weights unchanged", () => {
    const before = store.getState().weights["moneypuck"];
    store.getState().setWeight("nhl_com", 75);
    expect(store.getState().weights["moneypuck"]).toBe(before);
  });

  it("clamps weight to 0 minimum", () => {
    store.getState().setWeight("nhl_com", -10);
    expect(store.getState().weights["nhl_com"]).toBe(0);
  });

  it("clamps weight to 100 maximum", () => {
    store.getState().setWeight("nhl_com", 150);
    expect(store.getState().weights["nhl_com"]).toBe(100);
  });
});

describe("resetWeights", () => {
  let store: ReturnType<typeof makeStore>;
  beforeEach(() => {
    store = makeStore();
    store.getState().setSources([NHL, MP]);
  });

  it("resets all weights to equal distribution", () => {
    store.getState().setWeight("nhl_com", 90);
    store.getState().resetWeights();
    const w = store.getState().weights;
    expect(w["nhl_com"]).toBe(50);
    expect(w["moneypuck"]).toBe(50);
  });

  it("is a no-op when no sources loaded", () => {
    const fresh = makeStore();
    fresh.getState().resetWeights();
    expect(fresh.getState().weights).toEqual({});
  });
});

describe("activeWeights selector", () => {
  it("returns only sources with weight > 0", () => {
    const store = makeStore();
    store.getState().setSources([NHL, MP]);
    store.getState().setWeight("moneypuck", 0);
    const active = store.getState().activeWeights();
    expect("nhl_com" in active).toBe(true);
    expect("moneypuck" in active).toBe(false);
  });

  it("returns all weights when all are non-zero", () => {
    const store = makeStore();
    store.getState().setSources([NHL, MP]);
    const active = store.getState().activeWeights();
    expect(Object.keys(active)).toHaveLength(2);
  });
});
