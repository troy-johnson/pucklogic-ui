-- Milestone C (011a): token pass entitlements on subscriptions
-- Intentionally additive and nullable to represent users with no kit pass.

ALTER TABLE subscriptions
ADD COLUMN kit_pass_season TEXT,
ADD COLUMN kit_pass_purchased_at TIMESTAMPTZ;
