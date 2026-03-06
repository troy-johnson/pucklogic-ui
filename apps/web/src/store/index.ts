import { create } from "zustand";

// Root store — feature slices will be added here as they're built
// Example: import { createRankingsSlice, RankingsSlice } from "./rankings"
// type StoreState = RankingsSlice & ...

interface AppState {
  // placeholder — will be replaced by feature slices in Phase 2
  _initialized: boolean;
}

export const useStore = create<AppState>()(() => ({
  _initialized: true,
}));
