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

create unique index if not exists draft_sessions_one_active_per_user_idx
  on draft_sessions (user_id)
  where status = 'active';

create unique index if not exists draft_sessions_one_active_per_entitlement_idx
  on draft_sessions (entitlement_ref)
  where status = 'active' and entitlement_ref is not null;

create or replace function consume_draft_pass(p_user_id uuid, p_now timestamptz)
returns table (subscription_id uuid)
language plpgsql
security definer
set search_path = public
as $$
declare
  locked_subscription subscriptions%rowtype;
begin
  select *
  into locked_subscription
  from subscriptions
  where user_id = p_user_id
    and status = 'active'
    and draft_pass_balance > 0
    and (expires_at is null or expires_at > p_now)
  for update;

  if not found then
    return;
  end if;

  update subscriptions
  set draft_pass_balance = draft_pass_balance - 1
  where id = locked_subscription.id;

  return query
  select locked_subscription.id;
end;
$$;

create or replace function restore_draft_pass(p_subscription_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update subscriptions
  set draft_pass_balance = draft_pass_balance + 1
  where id = p_subscription_id;
end;
$$;

create or replace function credit_draft_pass_for_stripe_event(p_event_id text, p_user_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into stripe_processed_events (event_id)
  values (p_event_id)
  on conflict (event_id) do nothing;

  if not found then
    return false;
  end if;

  insert into subscriptions (user_id, plan, status, draft_pass_balance)
  values (p_user_id, 'draft_pass', 'active', 1)
  on conflict (user_id) do update
    set draft_pass_balance = subscriptions.draft_pass_balance + 1,
        status = 'active',
        expires_at = null;

  return true;
end;
$$;
