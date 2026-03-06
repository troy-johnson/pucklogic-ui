-- PuckLogic Phase 1/2 Schema
-- Run against your Supabase project via the Supabase SQL editor or CLI.

-- ---------------------------------------------------------------------------
-- players
-- Master list of NHL players.
-- ---------------------------------------------------------------------------
create table if not exists players (
  id          uuid primary key default gen_random_uuid(),
  nhl_id      integer unique not null,
  name        text not null,
  team        text,
  position    text,          -- C, LW, RW, D, G
  dob         date,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists players_position_idx on players (position);
create index if not exists players_team_idx     on players (team);

-- ---------------------------------------------------------------------------
-- sources
-- Registered ranking data sources.
-- ---------------------------------------------------------------------------
create table if not exists sources (
  id            uuid primary key default gen_random_uuid(),
  name          text unique not null,    -- machine key, e.g. "moneypuck"
  display_name  text not null,           -- human label, e.g. "MoneyPuck"
  url           text,
  scrape_config jsonb,
  active        boolean not null default true,
  created_at    timestamptz not null default now()
);

-- Seed known sources
insert into sources (name, display_name, url, active) values
  ('nhl_com',            'NHL.com',              'https://www.nhl.com',                        true),
  ('moneypuck',          'MoneyPuck',            'https://moneypuck.com',                      true),
  ('natural_stat_trick', 'Natural Stat Trick',   'https://www.naturalstattrick.com',           true),
  ('dobber',             'Dobber Hockey',        'https://dobberhockey.com',                   true),
  ('dom_luszczyszyn',    'Dom Luszczyszyn',      'https://theathletic.com',                    true),
  ('elite_prospects',    'Elite Prospects',      'https://www.eliteprospects.com',             true)
on conflict (name) do nothing;

-- ---------------------------------------------------------------------------
-- player_rankings
-- Per-source fantasy rankings per season.
-- ---------------------------------------------------------------------------
create table if not exists player_rankings (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players (id) on delete cascade,
  source_id   uuid not null references sources (id) on delete cascade,
  season      text not null,  -- e.g. "2025-26"
  rank        integer not null check (rank >= 1),
  score       numeric(8, 4),  -- normalized 0-1 score (optional, computed at read)
  scraped_at  timestamptz not null default now(),
  unique (player_id, source_id, season)
);

create index if not exists player_rankings_season_idx    on player_rankings (season);
create index if not exists player_rankings_source_idx    on player_rankings (source_id);
create index if not exists player_rankings_player_idx    on player_rankings (player_id);

-- ---------------------------------------------------------------------------
-- player_stats
-- Raw per-season stats for ML training and display.
-- ---------------------------------------------------------------------------
create table if not exists player_stats (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players (id) on delete cascade,
  season      text not null,
  games       integer,
  goals       integer,
  assists     integer,
  points      integer,
  toi_pg      numeric(5, 2),   -- time on ice per game (minutes)
  cf_pct      numeric(5, 2),   -- Corsi For %
  xgf_pct     numeric(5, 2),   -- Expected Goals For %
  pp_points   integer,
  sh_points   integer,
  scraped_at  timestamptz not null default now(),
  unique (player_id, season)
);

-- ---------------------------------------------------------------------------
-- player_trends
-- ML model output: breakout / regression signals.
-- ---------------------------------------------------------------------------
create table if not exists player_trends (
  id                uuid primary key default gen_random_uuid(),
  player_id         uuid not null references players (id) on delete cascade,
  season            text not null,
  breakout_score    numeric(5, 4),
  regression_risk   numeric(5, 4),
  confidence        numeric(5, 4),
  shap_values       jsonb,          -- per-feature SHAP explanations
  updated_at        timestamptz not null default now(),
  unique (player_id, season)
);

-- ---------------------------------------------------------------------------
-- user_kits
-- Saved user source-weight configurations.
-- ---------------------------------------------------------------------------
create table if not exists user_kits (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,   -- references auth.users(id) via RLS
  name        text not null,
  weights     jsonb not null,  -- {source_name: weight_float, ...}
  season      text not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists user_kits_user_idx on user_kits (user_id);

-- ---------------------------------------------------------------------------
-- draft_sessions
-- Live draft state for the browser extension.
-- ---------------------------------------------------------------------------
create table if not exists draft_sessions (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null,
  league_config  jsonb,
  picks          jsonb not null default '[]',
  available      jsonb not null default '[]',
  started_at     timestamptz not null default now(),
  ended_at       timestamptz,
  active         boolean not null default true
);

create index if not exists draft_sessions_user_idx on draft_sessions (user_id);

-- ---------------------------------------------------------------------------
-- exports
-- Tracks PDF / Excel export jobs.
-- ---------------------------------------------------------------------------
create table if not exists exports (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null,
  type         text not null check (type in ('pdf', 'excel')),
  status       text not null default 'pending' check (status in ('pending', 'complete', 'failed')),
  storage_url  text,
  created_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- subscriptions
-- Stripe subscription / purchase records.
-- ---------------------------------------------------------------------------
create table if not exists subscriptions (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null,
  stripe_customer_id  text,
  stripe_session_id   text unique,
  plan                text not null default 'draft_monitor',
  status              text not null default 'active',
  expires_at          timestamptz,
  created_at          timestamptz not null default now()
);

create index if not exists subscriptions_user_idx on subscriptions (user_id);
