/** Shared TypeScript types for PuckLogic — used by web app and (eventually) extension. */

export interface Source {
  id: string;
  name: string;
  display_name: string;
  url: string | null;
  active: boolean;
}

export interface RankedPlayer {
  composite_rank: number;
  composite_score: number;
  player_id: string;
  name: string;
  team: string;
  position: string;
  source_ranks: Record<string, number>;
}

export interface RankingsResult {
  season: string;
  computed_at: string;
  cached: boolean;
  rankings: RankedPlayer[];
}

export interface UserKit {
  id: string;
  name: string;
  season: string;
  weights: WeightsMap;
  created_at: string;
}

export type WeightsMap = Record<string, number>;

export interface ComputeRankingsRequest {
  season: string;
  weights: WeightsMap;
}

export interface CreateUserKitRequest {
  name: string;
  season: string;
  weights: WeightsMap;
}
