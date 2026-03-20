-- Migration 004: Add career totals columns for Hockey Reference incremental scraper.
-- HockeyReferenceScraper stores running career_goals and career_shots so that
-- scrape() can accumulate correctly without re-fetching full history.

alter table player_stats add column if not exists career_goals integer;
alter table player_stats add column if not exists career_shots integer;
