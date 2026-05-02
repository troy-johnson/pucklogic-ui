-- 010_session_close_rankings_snapshot.sql
-- Add persisted recipe inputs + close-time rankings snapshot fields to draft_sessions.

ALTER TABLE draft_sessions
  ADD COLUMN season TEXT,
  ADD COLUMN league_profile_id UUID,
  ADD COLUMN scoring_config_id UUID,
  ADD COLUMN source_weights JSONB,
  ADD COLUMN snapshot_rankings_at_close JSONB;
