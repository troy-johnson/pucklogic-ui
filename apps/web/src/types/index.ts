/** Shared TypeScript types for PuckLogic — used by web app and (eventually) extension. */

export interface Source {
  id: string;
  name: string;
  display_name: string;
  url: string | null;
  active: boolean;
  default_weight: number | null;
  is_paid: boolean;
}

export interface ProjectedStats {
  g: number | null;
  a: number | null;
  plus_minus: number | null;
  pim: number | null;
  ppg: number | null;
  ppa: number | null;
  ppp: number | null;
  shg: number | null;
  sha: number | null;
  shp: number | null;
  sog: number | null;
  fow: number | null;
  fol: number | null;
  hits: number | null;
  blocks: number | null;
  gp: number | null;
  gs: number | null;
  w: number | null;
  l: number | null;
  ga: number | null;
  sa: number | null;
  sv: number | null;
  sv_pct: number | null;
  so: number | null;
  otl: number | null;
}

export interface RankedPlayer {
  composite_rank: number;
  player_id: string;
  name: string;
  team: string | null;
  default_position: string | null;
  platform_positions: string[];
  projected_fantasy_points: number | null;
  vorp: number | null;
  schedule_score: number | null;
  off_night_games: number | null;
  source_count: number;
  projected_stats: ProjectedStats;
  breakout_score: number | null;
  regression_risk: number | null;
}

export interface RankingsResult {
  season: string;
  computed_at: string;
  cached: boolean;
  rankings: RankedPlayer[];
}

export interface ComputeRankingsRequest {
  season: string;
  source_weights: Record<string, number>;
  scoring_config_id: string;
  platform: string;
  league_profile_id?: string | null;
}

export interface ScoringConfig {
  id: string;
  name: string;
  stat_weights: Record<string, number>;
  is_preset: boolean;
}

export interface LeagueProfile {
  id: string;
  name: string;
  platform: string;
  num_teams: number;
  roster_slots: Record<string, number>;
  scoring_config_id: string;
  created_at: string;
}

export interface UserKit {
  id: string;
  name: string;
  source_weights: Record<string, number>;
  created_at: string;
}

export type WeightsMap = Record<string, number>;
