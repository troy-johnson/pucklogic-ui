-- Add completion audit fields to draft_sessions.
-- completion_reason distinguishes user-explicit end from inactivity expiry.
-- completed_at records when the session reached a terminal state.

alter table draft_sessions
  add column if not exists completion_reason text
    check (completion_reason in ('user_ended', 'inactivity_expired')),
  add column if not exists completed_at timestamptz;
