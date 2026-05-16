import { computeRankings } from "@/lib/api/rankings";
import { fetchScoringConfigPresets } from "@/lib/api/scoring-configs";
import { fetchSources } from "@/lib/api/sources";
import type { RankedPlayer, Source } from "@/types";

const DEFAULT_SEASON = "2025-26";
const DEFAULT_PLATFORM = "espn";

export interface InitialRankingsBundle {
  sources: Source[];
  rankings: RankedPlayer[];
  loadError: boolean;
  season: string;
  scoringConfigId: string | null;
  platform: string;
  sourceWeights: Record<string, number>;
}

/**
 * Server-side data load shared by /dashboard and /live.
 *
 * Fetches the active source list, default scoring preset, and computes
 * baseline rankings using equal source weights. Returns empty arrays with
 * `loadError = true` if any step fails so callers can surface a degraded
 * state instead of crashing the page.
 *
 * Pass the user's access token if any of the underlying endpoints require
 * authentication; safe to omit when called against public endpoints.
 */
export async function loadInitialRankings(
  token?: string,
): Promise<InitialRankingsBundle> {
  try {
    const [sources, presets] = await Promise.all([
      fetchSources(true, token),
      fetchScoringConfigPresets(token),
    ]);

    if (sources.length === 0 || presets.length === 0) {
      return {
        sources,
        rankings: [],
        loadError: false,
        season: DEFAULT_SEASON,
        scoringConfigId: presets[0]?.id ?? null,
        platform: DEFAULT_PLATFORM,
        sourceWeights: {},
      };
    }

    const equalShare = parseFloat((100 / sources.length).toFixed(10));
    const sourceWeights = Object.fromEntries(
      sources.map((s) => [s.name, equalShare]),
    );

    const result = await computeRankings(
      {
        season: DEFAULT_SEASON,
        source_weights: sourceWeights,
        scoring_config_id: presets[0].id,
        platform: DEFAULT_PLATFORM,
      },
      token,
    );

    return {
      sources,
      rankings: result.rankings,
      loadError: false,
      season: DEFAULT_SEASON,
      scoringConfigId: presets[0].id,
      platform: DEFAULT_PLATFORM,
      sourceWeights,
    };
  } catch (err) {
    console.error("[load-initial-rankings] failed:", err);
    return {
      sources: [],
      rankings: [],
      loadError: true,
      season: DEFAULT_SEASON,
      scoringConfigId: null,
      platform: DEFAULT_PLATFORM,
      sourceWeights: {},
    };
  }
}
