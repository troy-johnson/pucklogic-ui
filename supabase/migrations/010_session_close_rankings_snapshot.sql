-- 010_session_close_rankings_snapshot.sql
-- Add persisted recipe inputs + close-time rankings snapshot fields to draft_sessions.

ALTER TABLE draft_sessions
  ADD COLUMN season TEXT,
  ADD COLUMN league_profile_id UUID REFERENCES league_profiles(id),
  ADD COLUMN scoring_config_id UUID REFERENCES scoring_configs(id),
  ADD COLUMN source_weights JSONB,
  ADD COLUMN closing_rankings_snapshot JSONB;
