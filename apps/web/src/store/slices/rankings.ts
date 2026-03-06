import type { StateCreator } from "zustand";
import type { RankedPlayer, RankingsResult } from "@/types";

const DEFAULT_SEASON = "2025-26";

export interface RankingsSlice {
  season: string;
  rankings: RankedPlayer[];
  loading: boolean;
  error: string | null;
  cached: boolean;
  computedAt: string | null;

  setSeason: (season: string) => void;
  setRankings: (result: RankingsResult) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearRankings: () => void;
}

export const createRankingsSlice: StateCreator<RankingsSlice, [], [], RankingsSlice> = (
  set
) => ({
  season: DEFAULT_SEASON,
  rankings: [],
  loading: false,
  error: null,
  cached: false,
  computedAt: null,

  setSeason: (season) =>
    set({ season, rankings: [], error: null }),

  setRankings: (result) =>
    set({
      rankings: result.rankings,
      cached: result.cached,
      computedAt: result.computed_at,
      error: null,
      loading: false,
    }),

  setLoading: (loading) => set({ loading }),

  setError: (error) => set({ error, loading: false }),

  clearRankings: () =>
    set({ rankings: [], cached: false, computedAt: null }),
});
