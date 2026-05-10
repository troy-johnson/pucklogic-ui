import type { ScoringConfig } from "@/types";
import { apiFetch } from "./index";

export async function fetchScoringConfigPresets(
  token?: string,
): Promise<ScoringConfig[]> {
  return apiFetch<ScoringConfig[]>("/scoring-configs/presets", { token });
}
