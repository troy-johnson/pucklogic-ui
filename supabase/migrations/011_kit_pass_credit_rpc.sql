-- Milestone C (011a) follow-up: Stripe kit-pass webhook credit helper.
-- Ensures event-id idempotency and season-aware timestamp semantics.

create or replace function credit_kit_pass_for_stripe_event(
  p_event_id text,
  p_user_id uuid,
  p_season text,
  p_purchased_at timestamptz
)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  existing_subscription subscriptions%rowtype;
begin
  insert into stripe_processed_events (event_id)
  values (p_event_id)
  on conflict (event_id) do nothing;

  if not found then
    return 'already_processed';
  end if;

  select *
  into existing_subscription
  from subscriptions
  where user_id = p_user_id
  for update;

  if not found then
    insert into subscriptions (
      user_id,
      plan,
      status,
      expires_at,
      kit_pass_season,
      kit_pass_purchased_at
    ) values (
      p_user_id,
      'kit_pass',
      'active',
      null,
      p_season,
      p_purchased_at
    );
    return 'applied';
  end if;

  if existing_subscription.kit_pass_season is null then
    update subscriptions
    set kit_pass_season = p_season,
        kit_pass_purchased_at = p_purchased_at,
        status = 'active',
        expires_at = null
    where id = existing_subscription.id;
    return 'applied';
  end if;

  if existing_subscription.kit_pass_season = p_season then
    return 'noop_same_season';
  end if;

  if existing_subscription.kit_pass_season < p_season then
    update subscriptions
    set kit_pass_season = p_season,
        kit_pass_purchased_at = p_purchased_at,
        status = 'active',
        expires_at = null
    where id = existing_subscription.id;
    return 'overwrite_newer_season';
  end if;

  return 'stale_earlier_season';
end;
$$;
