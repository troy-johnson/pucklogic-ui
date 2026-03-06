import type { Source } from "@/types";
import { apiFetch } from "./index";

export async function fetchSources(activeOnly = true): Promise<Source[]> {
  return apiFetch<Source[]>(`/sources?active_only=${activeOnly}`);
}
