import type { StateCreator } from "zustand";
import type { DraftPick } from "@/types";

export type DraftMode = "sync" | "manual" | "reconnecting" | "disconnected";
export type DraftStatus = "idle" | "active" | "ended";

export interface DraftSessionSlice {
  sessionId: string | null;
  kitId: string | null;
  picks: DraftPick[];
  mode: DraftMode;
  status: DraftStatus;

  startSession: (payload: { sessionId: string; kitId: string }) => void;
  recordPick: (pick: DraftPick) => void;
  setMode: (mode: DraftMode) => void;
  endSession: () => void;
  reset: () => void;
}

const INITIAL_STATE = {
  sessionId: null,
  kitId: null,
  picks: [],
  mode: "sync" as DraftMode,
  status: "idle" as DraftStatus,
};

export const createDraftSessionSlice: StateCreator<
  DraftSessionSlice,
  [],
  [],
  DraftSessionSlice
> = (set) => ({
  ...INITIAL_STATE,

  startSession: ({ sessionId, kitId }) =>
    set({ sessionId, kitId, status: "active", picks: [], mode: "sync" }),

  recordPick: (pick) =>
    set((state) => ({ picks: [...state.picks, pick] })),

  setMode: (mode) => set({ mode }),

  endSession: () => set({ status: "ended", mode: "sync" }),

  reset: () => set(INITIAL_STATE),
});
