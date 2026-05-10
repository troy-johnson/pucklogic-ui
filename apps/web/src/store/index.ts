import { create } from "zustand";

import { createKitsSlice, type KitsSlice } from "./slices/kits";
import { createRankingsSlice, type RankingsSlice } from "./slices/rankings";
import { createSourcesSlice, type SourcesSlice } from "./slices/sources";

export type AppState = SourcesSlice & RankingsSlice & KitsSlice;

export const useStore = create<AppState>()((...a) => ({
  ...createSourcesSlice(...a),
  ...createRankingsSlice(...a),
  ...createKitsSlice(...a),
}));
