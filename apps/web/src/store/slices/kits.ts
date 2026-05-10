import type { StateCreator } from "zustand";
import type { UserKit } from "@/types";

export interface KitsSlice {
  kits: UserKit[];
  activeKitId: string | null;

  setKits: (kits: UserKit[]) => void;
  setActiveKit: (id: string | null) => void;
  addKit: (kit: UserKit) => void;
  removeKit: (id: string) => void;
  updateKit: (id: string, patch: Partial<UserKit>) => void;
}

export const createKitsSlice: StateCreator<KitsSlice, [], [], KitsSlice> = (
  set,
) => ({
  kits: [],
  activeKitId: null,

  setKits: (kits) => set({ kits }),

  setActiveKit: (id) => set({ activeKitId: id }),

  addKit: (kit) => set((state) => ({ kits: [...state.kits, kit] })),

  removeKit: (id) =>
    set((state) => ({
      kits: state.kits.filter((k) => k.id !== id),
      activeKitId: state.activeKitId === id ? null : state.activeKitId,
    })),

  updateKit: (id, patch) =>
    set((state) => ({
      kits: state.kits.map((k) => (k.id === id ? { ...k, ...patch } : k)),
    })),
});
