-- Add completion audit fields to draft_sessions.
-- completion_reason distinguishes user-explicit end from inactivity expiry.
-- completed_at records when the session reached a terminal state.

alter table draft_sessions
  add column if not exists completion_reason text
    check (completion_reason in ('user_ended', 'inactivity_expired')),
  add column if not exists completed_at timestamptz;

-- Add per-user draft pass balance to subscriptions.
-- Incremented by Stripe webhook on successful checkout; decremented on session start.

alter table subscriptions
  add column if not exists draft_pass_balance integer not null default 0
    check (draft_pass_balance >= 0);

-- Stripe webhook idempotency guard.
-- Processed event IDs are stored here so duplicate webhook deliveries do not
-- double-credit the user's draft pass balance.

create table if not exists stripe_processed_events (
    event_id   text        primary key,
    processed_at timestamptz not null default now()
);
