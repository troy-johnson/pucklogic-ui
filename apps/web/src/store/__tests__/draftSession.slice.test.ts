import { create } from "zustand";
import { beforeEach, describe, expect, it } from "vitest";

import {
  createDraftSessionSlice,
  type DraftSessionSlice,
} from "@/store/slices/draftSession";
import type { DraftPick } from "@/types";

const PICK: DraftPick = {
  playerId: "p1",
  playerName: "Connor McDavid",
  round: 1,
  pickNumber: 3,
  recordedAt: "2026-05-09T10:00:00Z",
};

function makeStore() {
  return create<DraftSessionSlice>()((...a) => ({
    ...createDraftSessionSlice(...a),
  }));
}

describe("DraftSessionSlice — initial state", () => {
  it("starts with null sessionId", () => {
    expect(makeStore().getState().sessionId).toBeNull();
  });

  it("starts with idle status", () => {
    expect(makeStore().getState().status).toBe("idle");
  });

  it("starts with empty picks", () => {
    expect(makeStore().getState().picks).toEqual([]);
  });

  it("starts with sync mode", () => {
    expect(makeStore().getState().mode).toBe("sync");
  });
});

describe("startSession", () => {
  it("sets sessionId and active status", () => {
    const store = makeStore();
    store.getState().startSession({ sessionId: "sess-1", kitId: "kit-1" });
    expect(store.getState().sessionId).toBe("sess-1");
    expect(store.getState().kitId).toBe("kit-1");
    expect(store.getState().status).toBe("active");
  });

  it("resets picks on session start", () => {
    const store = makeStore();
    store.getState().startSession({ sessionId: "s1", kitId: "k1" });
    store.getState().recordPick(PICK);
    store.getState().startSession({ sessionId: "s2", kitId: "k1" });
    expect(store.getState().picks).toHaveLength(0);
  });
});

describe("recordPick", () => {
  it("appends pick to picks array", () => {
    const store = makeStore();
    store.getState().startSession({ sessionId: "s1", kitId: "k1" });
    store.getState().recordPick(PICK);
    expect(store.getState().picks).toHaveLength(1);
    expect(store.getState().picks[0].playerId).toBe("p1");
  });

  it("accumulates multiple picks", () => {
    const store = makeStore();
    store.getState().startSession({ sessionId: "s1", kitId: "k1" });
    store.getState().recordPick({ ...PICK, playerId: "p1", pickNumber: 1 });
    store.getState().recordPick({ ...PICK, playerId: "p2", pickNumber: 2 });
    expect(store.getState().picks).toHaveLength(2);
  });
});

describe("hydrateSession", () => {
  it("populates sessionId, picks, and mode from server data", () => {
    const store = makeStore();
    store.getState().hydrateSession({
      sessionId: "sess-hydrate",
      picks: [PICK, { ...PICK, playerId: "p2", pickNumber: 4 }],
      mode: "manual",
    });
    expect(store.getState().sessionId).toBe("sess-hydrate");
    expect(store.getState().picks).toHaveLength(2);
    expect(store.getState().mode).toBe("manual");
    expect(store.getState().status).toBe("active");
  });

  it("sets kitId when provided in payload", () => {
    const store = makeStore();
    store.getState().hydrateSession({
      sessionId: "sess-1",
      kitId: "kit-from-server",
      picks: [],
      mode: "sync",
    });
    expect(store.getState().kitId).toBe("kit-from-server");
  });

  it("preserves existing kitId when payload omits kitId", () => {
    const store = makeStore();
    store.getState().startSession({ sessionId: "s0", kitId: "existing-kit" });
    store.getState().hydrateSession({
      sessionId: "sess-2",
      picks: [],
      mode: "sync",
    });
    expect(store.getState().kitId).toBe("existing-kit");
  });
});

describe("setMode", () => {
  it("updates the draft mode", () => {
    const store = makeStore();
    store.getState().setMode("manual");
    expect(store.getState().mode).toBe("manual");
  });

  it("can set reconnecting mode", () => {
    const store = makeStore();
    store.getState().setMode("reconnecting");
    expect(store.getState().mode).toBe("reconnecting");
  });
});

describe("endSession", () => {
  it("sets status to ended", () => {
    const store = makeStore();
    store.getState().startSession({ sessionId: "s1", kitId: "k1" });
    store.getState().endSession();
    expect(store.getState().status).toBe("ended");
  });

  it("resets mode to sync on end", () => {
    const store = makeStore();
    store.getState().setMode("manual");
    store.getState().endSession();
    expect(store.getState().mode).toBe("sync");
  });
});

describe("reset", () => {
  it("returns to initial state", () => {
    const store = makeStore();
    store.getState().startSession({ sessionId: "s1", kitId: "k1" });
    store.getState().recordPick(PICK);
    store.getState().setMode("manual");
    store.getState().reset();

    const s = store.getState();
    expect(s.sessionId).toBeNull();
    expect(s.kitId).toBeNull();
    expect(s.picks).toHaveLength(0);
    expect(s.mode).toBe("sync");
    expect(s.status).toBe("idle");
  });
});
