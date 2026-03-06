import { create } from "zustand";

import { createRankingsSlice, type RankingsSlice } from "./slices/rankings";
import { createSourcesSlice, type SourcesSlice } from "./slices/sources";

export type AppState = SourcesSlice & RankingsSlice;

export const useStore = create<AppState>()((...a) => ({
  ...createSourcesSlice(...a),
  ...createRankingsSlice(...a),
}));
