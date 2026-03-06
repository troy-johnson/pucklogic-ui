import type { ComputeRankingsRequest, RankingsResult } from "@/types";
import { apiFetch } from "./index";

export async function computeRankings(req: ComputeRankingsRequest): Promise<RankingsResult> {
  return apiFetch<RankingsResult>("/rankings/compute", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
