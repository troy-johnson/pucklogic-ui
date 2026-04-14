-- Align draft_sessions with the authoritative live-draft backend contract.
-- Safe to replace in-place because public.draft_sessions currently has zero rows.

drop policy if exists "Owner only" on draft_sessions;
drop table if exists draft_sessions;

create table if not exists draft_sessions (
  id                 uuid primary key default gen_random_uuid(),
  session_id         text not null unique,
  user_id            uuid not null references auth.users (id) on delete cascade,
  platform           text not null check (platform in ('espn', 'yahoo')),
  status             text not null default 'active' check (status in ('active', 'ended', 'expired')),
  entitlement_ref    text,
  sync_state         jsonb not null default '{"last_processed_pick": null, "sync_health": "healthy", "cursor": null}'::jsonb,
  accepted_picks     jsonb not null default '[]'::jsonb,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  last_heartbeat_at  timestamptz not null default now(),
  recovered_at       timestamptz
);

create unique index if not exists draft_sessions_one_active_per_user_idx
  on draft_sessions (user_id)
  where status = 'active';

create index if not exists draft_sessions_session_id_idx on draft_sessions (session_id);
create index if not exists draft_sessions_user_status_idx on draft_sessions (user_id, status);
create index if not exists draft_sessions_heartbeat_idx on draft_sessions (last_heartbeat_at);

alter table draft_sessions enable row level security;

create policy "Owner only" on draft_sessions
  for all using (auth.uid() = user_id);
