import { create } from "zustand";

import { createDraftSessionSlice, type DraftSessionSlice } from "./slices/draftSession";
import { createKitsSlice, type KitsSlice } from "./slices/kits";
import { createRankingsSlice, type RankingsSlice } from "./slices/rankings";
import { createSourcesSlice, type SourcesSlice } from "./slices/sources";

export type AppState = SourcesSlice & RankingsSlice & KitsSlice & DraftSessionSlice;

export const useStore = create<AppState>()((...a) => ({
  ...createSourcesSlice(...a),
  ...createRankingsSlice(...a),
  ...createKitsSlice(...a),
  ...createDraftSessionSlice(...a),
}));
