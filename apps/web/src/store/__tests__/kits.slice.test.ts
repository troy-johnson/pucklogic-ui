import { create } from "zustand";
import { beforeEach, describe, expect, it } from "vitest";

import { createKitsSlice, type KitsSlice } from "@/store/slices/kits";
import type { UserKit } from "@/types";

const KIT_A: UserKit = {
  id: "kit-a",
  name: "Kit A",
  source_weights: { nhl_com: 100 },
  created_at: "2026-01-01T00:00:00Z",
};
const KIT_B: UserKit = {
  id: "kit-b",
  name: "Kit B",
  source_weights: { moneypuck: 100 },
  created_at: "2026-01-02T00:00:00Z",
};

function makeStore() {
  return create<KitsSlice>()((...a) => ({ ...createKitsSlice(...a) }));
}

describe("KitsSlice — initial state", () => {
  it("starts with empty kits", () => {
    expect(makeStore().getState().kits).toEqual([]);
  });

  it("starts with null activeKitId", () => {
    expect(makeStore().getState().activeKitId).toBeNull();
  });
});

describe("setKits", () => {
  it("replaces the kits array", () => {
    const store = makeStore();
    store.getState().setKits([KIT_A, KIT_B]);
    expect(store.getState().kits).toHaveLength(2);
    expect(store.getState().kits[0].id).toBe("kit-a");
  });
});

describe("setActiveKit", () => {
  it("sets the activeKitId", () => {
    const store = makeStore();
    store.getState().setKits([KIT_A]);
    store.getState().setActiveKit("kit-a");
    expect(store.getState().activeKitId).toBe("kit-a");
  });

  it("accepts null to clear the active kit", () => {
    const store = makeStore();
    store.getState().setActiveKit("kit-a");
    store.getState().setActiveKit(null);
    expect(store.getState().activeKitId).toBeNull();
  });
});

describe("addKit", () => {
  it("appends a kit to the list", () => {
    const store = makeStore();
    store.getState().setKits([KIT_A]);
    store.getState().addKit(KIT_B);
    expect(store.getState().kits).toHaveLength(2);
    expect(store.getState().kits[1].id).toBe("kit-b");
  });
});

describe("removeKit", () => {
  it("removes the kit with the given id", () => {
    const store = makeStore();
    store.getState().setKits([KIT_A, KIT_B]);
    store.getState().removeKit("kit-a");
    expect(store.getState().kits).toHaveLength(1);
    expect(store.getState().kits[0].id).toBe("kit-b");
  });

  it("clears activeKitId when the active kit is removed", () => {
    const store = makeStore();
    store.getState().setKits([KIT_A]);
    store.getState().setActiveKit("kit-a");
    store.getState().removeKit("kit-a");
    expect(store.getState().activeKitId).toBeNull();
  });

  it("preserves activeKitId when a different kit is removed", () => {
    const store = makeStore();
    store.getState().setKits([KIT_A, KIT_B]);
    store.getState().setActiveKit("kit-b");
    store.getState().removeKit("kit-a");
    expect(store.getState().activeKitId).toBe("kit-b");
  });
});

describe("updateKit", () => {
  it("patches the kit with the given id", () => {
    const store = makeStore();
    store.getState().setKits([KIT_A]);
    store.getState().updateKit("kit-a", { name: "Renamed" });
    expect(store.getState().kits[0].name).toBe("Renamed");
    expect(store.getState().kits[0].source_weights).toEqual({ nhl_com: 100 });
  });

  it("does not modify other kits", () => {
    const store = makeStore();
    store.getState().setKits([KIT_A, KIT_B]);
    store.getState().updateKit("kit-a", { name: "Renamed" });
    expect(store.getState().kits[1].name).toBe("Kit B");
  });
});
