-- supabase/migrations/002_projection_aggregation.sql
-- Phase 2: Projection aggregation pipeline schema additions.
-- Recreates player_projections with per-stat columns + source_id FK.
-- Adds schedule_scores, player_platform_positions, league_profiles.
-- Adds default_weight, is_paid, user_id columns to sources.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- sources additions (must precede player_projections RLS that references sources.user_id)
-- ---------------------------------------------------------------------------
alter table sources add column if not exists default_weight float;
alter table sources add column if not exists is_paid boolean not null default false;
-- user_id references auth.users — set for user-uploaded custom sources, null for system sources
alter table sources add column if not exists user_id uuid references auth.users (id) on delete set null;

create index if not exists sources_user_idx on sources (user_id);

-- ---------------------------------------------------------------------------
-- player_projections (recreate with correct schema)
-- Per-source projected counting stats. source_id FK makes the unique
-- constraint (player_id, source_id, season) rather than (player_id, season).
-- null stat = source did not project this stat (≠ zero).
-- ---------------------------------------------------------------------------
drop table if exists player_projections;

create table player_projections (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players (id) on delete cascade,
  source_id   uuid not null references sources (id) on delete cascade,
  season      text not null,
  -- skater stats (all nullable — null means not projected)
  g           integer,
  a           integer,
  plus_minus  integer,
  pim         integer,
  ppg         integer,
  ppa         integer,
  ppp         integer,
  shg         integer,
  sha         integer,
  shp         integer,
  sog         integer,
  fow         integer,
  fol         integer,
  hits        integer,
  blocks      integer,
  gp          integer,
  -- goalie stats (all nullable)
  gs          integer,
  w           integer,
  l           integer,
  ga          integer,
  sa          integer,
  sv          integer,
  sv_pct      float,
  so          integer,
  otl         integer,
  -- overflow for source-specific stats not in the fixed set
  extra_stats jsonb,
  updated_at  timestamptz not null default now(),
  unique (player_id, source_id, season)
);

create index if not exists player_projections_player_idx on player_projections (player_id);
create index if not exists player_projections_season_idx on player_projections (season);
create index if not exists player_projections_source_idx on player_projections (source_id);

alter table player_projections enable row level security;
-- Read access filtered through source visibility: system sources (user_id IS NULL)
-- or the requesting user's own custom sources. Spec §7.6.
create policy "Read through visible sources" on player_projections
  for select using (
    exists (
      select 1 from sources
      where sources.id = player_projections.source_id
        and (sources.user_id is null or sources.user_id = auth.uid())
    )
  );
-- Writes restricted to service role (trusted backend ingestion paths only)
create policy "Service write" on player_projections
  for insert with check (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- sources — RLS policies per spec §7.6
-- ---------------------------------------------------------------------------
-- SELECT: system sources + own custom sources
drop policy if exists "Public read" on sources;
create policy "Visible sources read" on sources
  for select using (user_id is null or user_id = auth.uid());
-- INSERT/UPDATE/DELETE: only own custom sources
create policy "Owner manage custom sources" on sources
  for all using (user_id = auth.uid());
-- System rows (user_id IS NULL) remain read-only from user context

-- ---------------------------------------------------------------------------
-- schedule_scores
-- Off-night game counts per player per season.
-- "Off night" = a date where < 16 of 32 NHL teams play.
-- All stat columns are nullable: null = schedule not yet populated for that player.
-- ---------------------------------------------------------------------------
create table if not exists schedule_scores (
  player_id        uuid not null references players (id) on delete cascade,
  season           text not null,
  off_night_games  integer,              -- null until schedule ingestion runs
  total_games      integer,
  schedule_score   float,               -- min-max normalised 0–1; null until populated
  updated_at       timestamptz not null default now(),
  primary key (player_id, season)
);

create index if not exists schedule_scores_season_idx on schedule_scores (season);

alter table schedule_scores enable row level security;
create policy "Public read" on schedule_scores for select using (true);

-- ---------------------------------------------------------------------------
-- player_platform_positions
-- Platform-specific position eligibility — separate from players.position
-- (NHL.com canonical). Dual eligibility derived at query time.
-- ---------------------------------------------------------------------------
create table if not exists player_platform_positions (
  player_id  uuid not null references players (id) on delete cascade,
  platform   text not null,              -- 'espn', 'yahoo', 'fantrax'
  positions  text[] not null,            -- e.g. ['LW', 'RW']
  primary key (player_id, platform)
);

create index if not exists player_platform_positions_player_idx
  on player_platform_positions (player_id);
create index if not exists player_platform_positions_platform_idx
  on player_platform_positions (platform);

alter table player_platform_positions enable row level security;
create policy "Public read" on player_platform_positions for select using (true);

-- ---------------------------------------------------------------------------
-- league_profiles
-- Full league configuration needed to compute VORP.
-- ---------------------------------------------------------------------------
create table if not exists league_profiles (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null,
  name              text not null,
  platform          text not null check (platform in ('espn', 'yahoo', 'fantrax')),
  num_teams         integer not null check (num_teams > 0),
  roster_slots      jsonb not null,
  scoring_config_id uuid references scoring_configs (id),
  created_at        timestamptz not null default now()
);

create index if not exists league_profiles_user_idx on league_profiles (user_id);

alter table league_profiles enable row level security;
create policy "Owner only" on league_profiles for all using (auth.uid() = user_id);
