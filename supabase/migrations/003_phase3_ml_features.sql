-- supabase/migrations/003_phase3_ml_features.sql
-- Phase 3a: ML Trends Engine — schema additions for feature engineering and model output.
--
-- player_stats: adds Tier 1 advanced-stat columns, Tier 2/3 supplementary columns,
--               flag columns, and career-level stat columns required by the feature
--               engineering pipeline (docs/superpowers/specs/2026-03-18-phase3-ml-trends-design.md §3a).
--
-- player_trends: adds ML output columns for breakout/regression signals, SHAP top-3,
--                and projection metadata (spec §3c).
--
-- All statements are idempotent (ADD COLUMN IF NOT EXISTS).
-- Existing columns (cf_pct, xgf_pct, iscf_per_60, toi_per_game, pp_toi_pg, war) are
-- retained unchanged — the new columns are distinct metrics used by the feature pipeline.
-- ---------------------------------------------------------------------------

-- ===========================================================================
-- player_stats — Tier 1 core ML features
-- ===========================================================================
--
-- NOTE: Several Tier 1 features are already present from 001_initial_schema.sql:
--   sh_pct         (shooting % — used to compute sh_pct_delta = sh_pct - sh_pct_career_avg)
--   pdo            (SH% + SV% luck indicator)
--   toi_per_game   (total TOI per game — distinct from toi_ev, toi_pp, toi_sh added below)
--   pp_toi_pg      (PP TOI per game — distinct from toi_pp added below, may differ in source)
--   cf_pct         (raw Corsi For % — distinct from cf_pct_adj added below)
--   xgf_pct        (expected goals % — distinct from xgf_pct_5v5 added below)
--   iscf_per_60    (legacy scoring chances — NOT read by Phase 3 pipeline; see scf_per60 below)
--   war            (wins above replacement — distinct from gar/xgar added below)
--
-- Computed at query time (not stored):
--   age            (from players.date_of_birth)
--   sh_pct_delta   (sh_pct − sh_pct_career_avg; derived in feature pipeline)

-- Individual Corsi For per 60 min (shot volume).
-- Multicollinearity: do NOT include alongside ixg_per60 (one volume metric is sufficient)
-- or isf_per60 (individual shots for — collinear per feature spec §Multicollinearity Warnings).
-- Distinct from existing iscf_per_60 (individual scoring chances — a different metric).
alter table player_stats add column if not exists icf_per60 float;

-- Individual expected goals per 60 min (shot quality; pair with icf_per60)
alter table player_stats add column if not exists ixg_per60 float;

-- Goals minus individual xG — primary breakout/regression signal
-- Negative = buy (shooting below xG); positive = sell
alter table player_stats add column if not exists g_minus_ixg float;

-- On-ice xGF% at 5v5, score-adjusted — best single play-driving metric
-- Distinct from existing xgf_pct (not 5v5-isolated or score-adjusted)
alter table player_stats add column if not exists xgf_pct_5v5 float;

-- Score-and-venue-adjusted Corsi For % — highest repeatability (~10 games)
-- Distinct from existing cf_pct (raw, unadjusted)
alter table player_stats add column if not exists cf_pct_adj float;

-- On-ice scoring chance % (outperforms CF% and xG for offensive prediction)
alter table player_stats add column if not exists scf_pct float;

-- Individual scoring chances per 60 min (most predictive for future goals).
-- The existing iscf_per_60 column remains written by the legacy NST scraper path but is NOT
-- read by the Phase 3 feature pipeline. Do not deprecate iscf_per_60 until the scraper
-- migration to scf_per60 is verified complete and all tests pass.
alter table player_stats add column if not exists scf_per60 float;

-- Primary points (G + A1) per 60 min — strips near-random A2 noise
alter table player_stats add column if not exists p1_per60 float;

-- Even-strength TOI per game (minutes). Distinct from toi_per_game (total TOI, all situations).
-- NOTE: docs/feature-engineering-spec.md names this feature toi_ev_per_game. The feature
-- engineering pipeline (transforms.py) must alias toi_ev → toi_ev_per_game when building
-- the feature matrix to match the spec's column naming.
alter table player_stats add column if not exists toi_ev float;

-- Power play TOI per game (minutes). Distinct from pp_toi_pg (may differ in source/normalisation).
-- NOTE: spec names this toi_pp_per_game — pipeline must alias accordingly.
alter table player_stats add column if not exists toi_pp float;

-- Short-handed TOI per game (minutes).
-- NOTE: spec names this toi_sh_per_game — pipeline must alias accordingly.
alter table player_stats add column if not exists toi_sh float;

-- PP unit designation: 1 = PP1, 2 = PP2, 0 = no PP time. Written by DailyFaceoff scraper.
-- Season-level aggregate (most recent assignment per season).
-- The per-day snapshot lives in player_lines.pp_unit (Layer 2 source). The feature pipeline
-- reads player_stats.pp_unit for training; player_lines is the Layer 2 signal source.
alter table player_stats add column if not exists pp_unit smallint;

-- Inline CHECK omitted to preserve ADD COLUMN IF NOT EXISTS idempotency.
-- Named constraint added separately below so it can be applied conditionally.
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'player_stats_pp_unit_valid'
    and conrelid = 'player_stats'::regclass
  ) then
    alter table player_stats add constraint player_stats_pp_unit_valid
      check (pp_unit in (0, 1, 2));
  end if;
end $$;

-- Rolling career SH% (Hockey Reference) — used to derive sh_pct_delta in the feature pipeline.
-- Formula: sh_pct_delta = sh_pct (current season) - sh_pct_career_avg (career average, not single-season).
alter table player_stats add column if not exists sh_pct_career_avg float;

-- ===========================================================================
-- player_stats — Tier 2 supplementary ML features
-- ===========================================================================

-- CF% relative to team when player is off ice (drop if using RAPM)
alter table player_stats add column if not exists cf_pct_rel float;

-- Goals Above Replacement — use for forwards (Evolving Hockey, manual annual pull)
-- Distinct from existing war column (different methodology)
alter table player_stats add column if not exists gar float;

-- Expected Goals Above Replacement — use for defensemen (Evolving Hockey)
alter table player_stats add column if not exists xgar float;

-- Expected goals against per 60 min on-ice (defensive evaluation)
alter table player_stats add column if not exists xga_per60 float;

-- Goals per 60 min (moderate stability; p1_per60 subsumes most of this signal)
alter table player_stats add column if not exists g_per60 float;

-- Primary assists per 60 min
alter table player_stats add column if not exists a1_per60 float;

-- Power play points per 60 PP minutes (pair with toi_pp and pp_unit)
alter table player_stats add column if not exists ppp_per60 float;

-- Years played in NHL (interacts with age for aging curve calibration)
alter table player_stats add column if not exists nhl_experience integer;

-- Faceoff win % (only for leagues scoring faceoffs)
alter table player_stats add column if not exists fo_pct float;

-- ===========================================================================
-- player_stats — Tier 3 situational features
-- ===========================================================================

-- Speed bursts ≥22 mph per game (NHL EDGE, optional — only 5 seasons of data)
alter table player_stats add column if not exists speed_bursts_22 float;

-- Max skating speed recorded (best aging indicator in EDGE data)
alter table player_stats add column if not exists top_speed float;

-- Offensive zone start % (modest adjustment value)
alter table player_stats add column if not exists ozs_pct float;

-- On-ice shooting % while on ice (regression signal; 96.4% don't repeat >11%)
alter table player_stats add column if not exists oi_sh_pct float;

-- ===========================================================================
-- player_stats — flag columns (boolean context signals)
-- ===========================================================================

-- Entry-level contract flag (14+ ES min/game → 43% breakout probability uplift)
alter table player_stats add column if not exists elc_flag boolean not null default false;

-- Player in final year of contract (weak signal, statistically insignificant in aggregate)
alter table player_stats add column if not exists contract_year_flag boolean not null default false;

-- Player signed new contract this season (negative signal; production declines 73% of cases)
alter table player_stats add column if not exists post_extension_flag boolean not null default false;

-- New head coach this season (material impact ±1 WAR; requires manual maintenance)
alter table player_stats add column if not exists coaching_change_flag boolean not null default false;

-- Player traded in/out in offseason (context change; direction-dependent)
alter table player_stats add column if not exists trade_flag boolean not null default false;

-- ===========================================================================
-- player_stats — indexes
-- ===========================================================================

create index if not exists player_stats_season_idx on player_stats (season);
create index if not exists player_stats_pp_unit_idx on player_stats (pp_unit) where pp_unit is not null;

-- ===========================================================================
-- player_trends — ML output columns
-- ===========================================================================

-- Which breakout signals fired (JSONB map of signal_name → bool)
-- e.g. {"g_below_ixg": true, "pp_promotion": true, "prime_age_window": false, ...}
alter table player_trends add column if not exists breakout_signals jsonb;

-- Which regression signals fired (same structure)
alter table player_trends add column if not exists regression_signals jsonb;

-- Top 3 SHAP contributors for UI display (subset of shap_values for quick rendering)
-- e.g. {"breakout": [["g_minus_ixg", 0.18], ["pp_unit", 0.12], ["sh_pct_delta", -0.09]]}
-- Full per-feature SHAP is in the existing shap_values column
alter table player_trends add column if not exists shap_top3 jsonb;

-- Projected fantasy points output from the projection pipeline
alter table player_trends add column if not exists projection_pts float;

-- Projection tier from the rule-based breakout/regression signal count (NOT model confidence).
-- 'HIGH' = 4+ signals fired, 'MEDIUM' = 3, 'LOW' = 2.
-- Distinct from the `confidence` column (XGBoost max class probability).
-- See docs/feature-engineering-spec.md §Projection Pipeline step 7.
alter table player_trends add column if not exists projection_tier text;

-- Named constraint added separately for idempotency (same pattern as pp_unit above).
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'player_trends_projection_tier_valid'
    and conrelid = 'player_trends'::regclass
  ) then
    alter table player_trends add constraint player_trends_projection_tier_valid
      check (projection_tier in ('HIGH', 'MEDIUM', 'LOW'));
  end if;
end $$;

-- ===========================================================================
-- player_trends — indexes
-- ===========================================================================

-- Composite indexes keyed by season first so WHERE season = ? ORDER BY score
-- can be satisfied with a single index scan (no cross-season filter + sort).
create index if not exists player_trends_season_breakout_idx
  on player_trends (season, breakout_score desc nulls last)
  where breakout_score is not null;
create index if not exists player_trends_season_regression_idx
  on player_trends (season, regression_risk desc nulls last)
  where regression_risk is not null;
