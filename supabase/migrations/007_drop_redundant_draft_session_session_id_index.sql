-- Remove the redundant non-unique session_id index.
-- draft_sessions.session_id already has a unique constraint-backed index.

drop index if exists draft_sessions_session_id_idx;
