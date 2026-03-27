-- 005_hits_blocks_per60.sql
-- Adds per-60 physical rate columns needed by the ML feature pipeline.
-- hits and blocks (raw totals) already exist from Phase 1.

alter table player_stats
  add column if not exists hits_per60   float,
  add column if not exists blocks_per60 float;
