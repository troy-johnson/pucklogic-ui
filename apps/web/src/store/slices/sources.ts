import type { StateCreator } from "zustand";
import type { Source, WeightsMap } from "@/types";

export interface SourcesSlice {
  sources: Source[];
  weights: WeightsMap;

  /** Replace the source list and reset weights to equal distribution. */
  setSources: (sources: Source[]) => void;
  /** Update a single source's weight (clamped to [0, 100]). */
  setWeight: (name: string, value: number) => void;
  /** Reset all weights to equal distribution based on current sources. */
  resetWeights: () => void;
  /** Returns only sources whose weight is > 0. */
  activeWeights: () => WeightsMap;
}

function equalWeights(sources: Source[]): WeightsMap {
  if (sources.length === 0) return {};
  const share = parseFloat((100 / sources.length).toFixed(10));
  return Object.fromEntries(sources.map((s) => [s.name, share]));
}

export const createSourcesSlice: StateCreator<SourcesSlice, [], [], SourcesSlice> = (
  set,
  get
) => ({
  sources: [],
  weights: {},

  setSources: (sources) =>
    set({ sources, weights: equalWeights(sources) }),

  setWeight: (name, value) =>
    set((state) => ({
      weights: { ...state.weights, [name]: Math.min(100, Math.max(0, value)) },
    })),

  resetWeights: () =>
    set((state) => ({ weights: equalWeights(state.sources) })),

  activeWeights: () => {
    const { weights } = get();
    return Object.fromEntries(Object.entries(weights).filter(([, v]) => v > 0));
  },
});
