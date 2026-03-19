-- PuckLogic — Initial Schema
-- Source of truth: docs/backend-reference.md
-- Additions beyond reference DDL: injury_reports, scraper_logs, player_lines
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- players
-- NHL player master. nhl_id is the canonical cross-source key.
-- ---------------------------------------------------------------------------
create table if not exists players (
  id             uuid primary key default gen_random_uuid(),
  nhl_id         integer unique,
  name           text not null,
  team           text,
  position       text,                    -- C, LW, RW, D (skaters only at launch)
  date_of_birth  date,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index if not exists players_position_idx on players (position);
create index if not exists players_team_idx     on players (team);

-- ---------------------------------------------------------------------------
-- player_aliases
-- Maps name variants to canonical player_id for cross-source matching.
-- Populated by the scraper matching pipeline (rapidfuzz fuzzy match).
-- ---------------------------------------------------------------------------
create table if not exists player_aliases (
  id         uuid primary key default gen_random_uuid(),
  player_id  uuid not null references players (id) on delete cascade,
  alias_name text not null,
  source     text,                        -- which source uses this name variant
  unique (alias_name, source)
);

create index if not exists player_aliases_player_idx on player_aliases (player_id);
create index if not exists player_aliases_name_idx   on player_aliases (alias_name);

-- ---------------------------------------------------------------------------
-- sources
-- Registered ranking data sources.
-- ---------------------------------------------------------------------------
create table if not exists sources (
  id                     uuid primary key default gen_random_uuid(),
  name                   text unique not null,    -- machine key, e.g. "moneypuck"
  display_name           text not null,           -- human label, e.g. "MoneyPuck"
  url                    text,
  scrape_config          jsonb,
  active                 boolean not null default true,
  last_successful_scrape timestamptz,
  created_at             timestamptz not null default now()
);

-- Seed known sources
insert into sources (name, display_name, url, active) values
  ('nhl_com',            'NHL.com',            'https://www.nhl.com',                  true),
  ('moneypuck',          'MoneyPuck',          'https://moneypuck.com',                true),
  ('natural_stat_trick', 'Natural Stat Trick', 'https://www.naturalstattrick.com',     true),
  ('dobber',             'Dobber Hockey',      'https://dobberhockey.com',             true),
  ('dom_luszczyszyn',    'Dom Luszczyszyn',    'https://theathletic.com',              true),
  ('elite_prospects',    'Elite Prospects',    'https://www.eliteprospects.com',       true)
on conflict (name) do nothing;

-- ---------------------------------------------------------------------------
-- player_rankings
-- Per-source fantasy rankings per season.
-- Written via staging → atomic swap, never directly.
-- ---------------------------------------------------------------------------
create table if not exists player_rankings (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players (id) on delete cascade,
  source_id   uuid not null references sources (id) on delete cascade,
  rank        integer not null check (rank >= 1),
  score       float,                      -- normalized 0–1 (computed at ingest)
  season      text not null,             -- e.g. "2026-27"
  scraped_at  timestamptz not null default now(),
  unique (player_id, source_id, season)
);

create index if not exists player_rankings_season_idx on player_rankings (season);
create index if not exists player_rankings_source_idx on player_rankings (source_id);
create index if not exists player_rankings_player_idx on player_rankings (player_id);

-- ---------------------------------------------------------------------------
-- player_rankings_staging
-- Staging table for atomic swap. Scrapers write here; promote_to_production()
-- does a single-transaction DELETE + INSERT into player_rankings on success.
-- ---------------------------------------------------------------------------
create table if not exists player_rankings_staging (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players (id) on delete cascade,
  source_id   uuid not null references sources (id) on delete cascade,
  rank        integer not null check (rank >= 1),
  score       float,
  season      text not null,
  scraped_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- player_stats
-- Raw per-season stats — inputs for ML training and display.
-- ---------------------------------------------------------------------------
create table if not exists player_stats (
  id            uuid primary key default gen_random_uuid(),
  player_id     uuid not null references players (id) on delete cascade,
  season        text not null,
  gp            integer,                  -- games played
  g             integer,                  -- goals
  a             integer,                  -- assists
  pts           integer,                  -- points
  ppp           integer,                  -- power play points
  sh_points     integer,                  -- short-handed points
  toi_per_game  float,                   -- total TOI per game (minutes)
  pp_toi_pg     float,                   -- power play TOI per game (minutes)
  sog           integer,                  -- shots on goal
  hits          integer,
  blocks        integer,
  cf_pct        float,                   -- Corsi For %
  xgf_pct       float,                   -- Expected Goals For %
  iscf_per_60   float,                   -- individual scoring chances per 60 (key breakout predictor)
  sh_pct        float,                   -- shooting % (regression signal)
  pdo           float,                   -- SH% + SV% luck indicator (regresses to ~1.000)
  war           float,                   -- wins above replacement (Evolving Hockey)
  scraped_at    timestamptz not null default now(),
  unique (player_id, season)
);

-- ---------------------------------------------------------------------------
-- player_trends
-- Layer 1 ML output: pre-season breakout / regression scores.
-- Phase 3 Layer 1 ML output columns (breakout_signals, shap_top3, projection_pts, etc.)
-- added in 003_phase3_ml_features.sql.
-- Layer 2 columns (trending_up_score, momentum_score, signals_json) deferred to v2.0.
-- ---------------------------------------------------------------------------
create table if not exists player_trends (
  id               uuid primary key default gen_random_uuid(),
  player_id        uuid not null references players (id) on delete cascade,
  season           text not null,
  breakout_score   float,                -- 0–1 probability of breakout
  regression_risk  float,                -- 0–1 probability of regression
  confidence       float,                -- model confidence score
  shap_values      jsonb,               -- pre-computed SHAP explanations per feature
  updated_at       timestamptz not null default now(),
  unique (player_id, season)
);

-- ---------------------------------------------------------------------------
-- player_projections
-- Projected counting stats per player per season.
-- ---------------------------------------------------------------------------
create table if not exists player_projections (
  id               uuid primary key default gen_random_uuid(),
  player_id        uuid not null references players (id) on delete cascade,
  season           text not null,
  projected_stats  jsonb,               -- {g: 30, a: 45, pts: 75, ppp: 20, sog: 250, ...}
  scoring_basis    text,                -- e.g. "rate_adjusted_2yr_avg"
  updated_at       timestamptz not null default now(),
  unique (player_id, season)
);

-- ---------------------------------------------------------------------------
-- scoring_configs
-- Fantasy scoring presets (is_preset = true, user_id = null) and
-- user-saved custom configs (is_preset = false, user_id set).
-- ---------------------------------------------------------------------------
create table if not exists scoring_configs (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  stat_weights  jsonb not null,         -- {g: 3, a: 2, ppp: 1, sog: 0.5, ...}
  is_preset     boolean not null default false,
  user_id       uuid,                   -- null for system presets
  created_at    timestamptz not null default now()
);

create index if not exists scoring_configs_user_idx on scoring_configs (user_id);

-- Seed standard scoring presets
insert into scoring_configs (name, stat_weights, is_preset) values
  ('Standard Points', '{"g":3,"a":2,"ppp":1,"shp":2,"sog":0,"hits":0,"blocks":0}', true),
  ('Points + Peripherals', '{"g":3,"a":2,"ppp":1,"shp":2,"sog":0.5,"hits":0.5,"blocks":0.5}', true),
  ('Standard Roto', '{"g":1,"a":1,"ppp":1,"sog":1,"hits":1,"blocks":1,"plus_minus":1}', true)
on conflict do nothing;

-- ---------------------------------------------------------------------------
-- user_kits
-- Named source-weight presets only. Full league config (platform, scoring,
-- roster) lives in league_profiles. Supports authenticated and anonymous users.
-- ---------------------------------------------------------------------------
create table if not exists user_kits (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid,              -- null for anonymous sessions
  session_token   uuid,              -- for anonymous kit building (cookie-based)
  name            text,
  source_weights  jsonb not null,   -- {source_id: weight_float, ...}
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  check (user_id is not null or session_token is not null)
);

create index if not exists user_kits_user_idx    on user_kits (user_id);
create index if not exists user_kits_session_idx on user_kits (session_token);

-- ---------------------------------------------------------------------------
-- draft_sessions
-- Live draft state for the browser extension.
-- ---------------------------------------------------------------------------
create table if not exists draft_sessions (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null,
  platform      text not null check (platform in ('espn', 'yahoo')),
  league_config jsonb,
  picks         jsonb not null default '[]',
  available     jsonb not null default '[]',
  kit_id        uuid references user_kits (id),
  status        text not null default 'active' check (status in ('active', 'completed', 'expired')),
  activated_at  timestamptz not null default now(),
  expires_at    timestamptz
);

create index if not exists draft_sessions_user_idx on draft_sessions (user_id);

-- ---------------------------------------------------------------------------
-- exports
-- Tracks async PDF / Excel / bundle export jobs.
-- ---------------------------------------------------------------------------
create table if not exists exports (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null,
  type         text not null check (type in ('pdf', 'excel', 'bundle')),
  status       text not null default 'pending' check (status in ('pending', 'generating', 'complete', 'failed')),
  storage_url  text,
  created_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- subscriptions
-- Stripe subscription / purchase records. Written by webhook via service role.
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

-- ---------------------------------------------------------------------------
-- injury_reports
-- One row per player (upserted daily). Feeds Layer 2 "return from injury" signal.
-- ---------------------------------------------------------------------------
create table if not exists injury_reports (
  id           uuid primary key default gen_random_uuid(),
  player_id    uuid not null references players (id) on delete cascade,
  status       text not null check (status in ('healthy', 'day-to-day', 'week-to-week', 'ir', 'ltir')),
  description  text,
  updated_at   timestamptz not null default now(),
  unique (player_id)
);

create index if not exists injury_reports_status_idx on injury_reports (status);

-- ---------------------------------------------------------------------------
-- scraper_logs
-- Per-run audit trail for the admin scraper health dashboard.
-- ---------------------------------------------------------------------------
create table if not exists scraper_logs (
  id             uuid primary key default gen_random_uuid(),
  scraper_name   text not null,
  status         text not null check (status in ('running', 'success', 'failed')),
  started_at     timestamptz not null default now(),
  completed_at   timestamptz,
  rows_inserted  integer,
  error_message  text,
  traceback      text
);

create index if not exists scraper_logs_scraper_idx on scraper_logs (scraper_name);
create index if not exists scraper_logs_started_idx on scraper_logs (started_at desc);

-- ---------------------------------------------------------------------------
-- player_lines
-- Daily line/unit assignments — EV, PP, PK context.
-- One row per player per day. Primary Layer 2 signal source.
-- ---------------------------------------------------------------------------
create table if not exists player_lines (
  id              uuid primary key default gen_random_uuid(),
  player_id       uuid not null references players (id) on delete cascade,
  season          text not null,
  date            date not null,

  -- Even strength
  ev_line         smallint check (ev_line between 1 and 4),   -- F: 1=top line…4=4th; D: 1–3
  ev_toi_pg       numeric(5, 2),                              -- EV TOI per game for this stretch
  ev_linemate_ids uuid[],                                     -- other skaters on this unit

  -- Power play
  pp_unit         smallint check (pp_unit between 1 and 2),   -- null = not on PP
  pp_toi_pg       numeric(5, 2),
  pp_linemate_ids uuid[],

  -- Penalty kill
  pk_unit         smallint check (pk_unit between 1 and 2),   -- null = not on PK
  pk_toi_pg       numeric(5, 2),
  pk_linemate_ids uuid[],

  source          text not null,                              -- e.g. 'dailyfaceoff'
  recorded_at     timestamptz not null default now(),

  unique (player_id, date)
);

create index if not exists player_lines_player_idx on player_lines (player_id);
create index if not exists player_lines_season_idx on player_lines (season);
create index if not exists player_lines_date_idx   on player_lines (date desc);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

-- Public NHL data: anyone can read; only service role can write.
alter table players                  enable row level security;
alter table player_aliases           enable row level security;
alter table sources                  enable row level security;
alter table player_rankings          enable row level security;
alter table player_rankings_staging  enable row level security;
alter table player_stats             enable row level security;
alter table player_trends            enable row level security;
alter table player_projections       enable row level security;
alter table injury_reports           enable row level security;
alter table player_lines             enable row level security;

create policy "Public read" on players               for select using (true);
create policy "Public read" on player_aliases        for select using (true);
create policy "Public read" on sources               for select using (true);
create policy "Public read" on player_rankings       for select using (true);
create policy "Public read" on player_stats          for select using (true);
create policy "Public read" on player_trends         for select using (true);
create policy "Public read" on player_projections    for select using (true);
create policy "Public read" on injury_reports        for select using (true);
create policy "Public read" on player_lines          for select using (true);

-- Restrict writes on public tables to service role only.
create policy "Service write" on player_rankings
  for insert with check (auth.role() = 'service_role');
create policy "Service write" on player_rankings_staging
  for insert with check (auth.role() = 'service_role');
create policy "Service write" on player_stats
  for insert with check (auth.role() = 'service_role');
create policy "Service write" on player_trends
  for insert with check (auth.role() = 'service_role');
create policy "Service write" on player_projections
  for insert with check (auth.role() = 'service_role');

-- scoring_configs: presets are public read; custom configs are owner-only.
alter table scoring_configs enable row level security;

create policy "Public preset read" on scoring_configs
  for select using (is_preset = true);

create policy "Owner read custom" on scoring_configs
  for select using (auth.uid() = user_id);

create policy "Owner manage custom" on scoring_configs
  for all using (auth.uid() = user_id);

-- user_kits: owner or matching anonymous session token.
alter table user_kits enable row level security;

create policy "Owner or session" on user_kits
  for all using (
    auth.uid() = user_id
    or session_token = (current_setting('request.cookies', true)::jsonb ->> 'pucklogic_session')::uuid
  );

-- draft_sessions: owner only.
alter table draft_sessions enable row level security;

create policy "Owner only" on draft_sessions
  for all using (auth.uid() = user_id);

-- exports: owner can create and read their own jobs.
alter table exports enable row level security;

create policy "Owner read" on exports
  for select using (auth.uid() = user_id);

create policy "Owner create" on exports
  for insert with check (auth.uid() = user_id);

-- subscriptions: owner can read; Stripe webhook writes via service role.
alter table subscriptions enable row level security;

create policy "Owner read" on subscriptions
  for select using (auth.uid() = user_id);

-- scraper_logs: service role only — no client access.
alter table scraper_logs enable row level security;
