import type { ScoringConfig } from "@/types";
import { apiFetch } from "./index";

export async function fetchScoringConfigPresets(): Promise<ScoringConfig[]> {
  return apiFetch<ScoringConfig[]>("/scoring-configs/presets");
}
