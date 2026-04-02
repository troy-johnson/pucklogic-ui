| Field | Value |
|---|---|
| Active Phase | Scraper data quality hardening closeout on `feat/scraper-data-quality`; Hockey Reference dedup fix landed locally and verification is complete |
| Active Branch | feat/scraper-data-quality |
| Open PR | None |
| Current Focus | Keep axon-state and Notion aligned as canonical status sources, then move to draft-kit workflow/UI scope lock |
| Last Action | Merged PR #30 after syncing Notion readiness/status pages to the post-ML-run state and verifying Hockey Reference dedup hardening, scraper tests, and 2024-25 data-quality coverage |
| Pending External | Legal/commercial review of third-party aggregated data usage before monetized extension launch |
| Current Hypothesis | HR multi-team/career dedup risk is now mitigated by stable player-key parsing, so remaining risk is review/merge coordination rather than scraper correctness |
| Next Steps | 1. Lock draft-kit workflow/UI scope 2. Start backend integration verification for the launch flow 3. Keep Notion and axon-state synced during product build |

## Backfill/data quality completion status (current)

- Migration `005_hits_blocks_per60` applied to production Supabase project `mrjrtwwmbxfytnnjkaid`
- `scripts/backfill_data_quality.sh` added with staged flow:
  - sample run
  - validation gate
  - full run
  - final validation
- Split historical coverage now enforced operationally:
  - NHL.com raw hits/blocks: `2005-06` onward
  - NST `hits_per60` / `blocks_per60`: `2007-08` onward (NST has no usable rows in `2005-06` and `2006-07`)
- Validation rules now use source-correct TOI checks (non-negative situation TOI values), not `toi_sh < toi_ev`
- Upserts to `player_stats` now use `default_to_null=False` to avoid partial payloads nulling existing columns

## Verified outcomes

- Targeted scraper tests passing after fixes:
  - `pytest tests/scrapers/test_nst.py tests/scrapers/test_nhl_com.py` → 85 passed
- Targeted season reruns completed after upsert fix:
  - NST `2009-10..2009-10`
  - NHL.com `2009-10..2009-10`
  - NHL.com `2024-25..2024-25`
- Season-level DB validation now shows:
  - Raw coverage strong from `2005-06` onward
  - Rate coverage strong from `2007-08` onward, including corrected `2009-10`
  - No negative `toi_ev` / `toi_pp` / `toi_sh` values
  - `2026-27` empty is acceptable because season not started

## Decisions now in force

- NHL.com summary/realtime backfills remain `isAggregate=true`
- NST per-60 historical floor is operationally `2007-08`
- Web draft kit remains primary launch target; extension remains secondary and non-blocking for web launch
- Auth + saved kits remain required launch scope for the web product
- First real ML run should happen immediately after remaining scraper hardening (Hockey Reference dedup) closes

## Execution outcomes (2026-03-29)

- HR targeted verification backfill succeeded (`2009-10..2010-11`, 336 rows).
- First real ML run succeeded for `2026-27` (dataset 11229, artifacts uploaded, `player_trends` 901 rows).
- Trends endpoint now returns stable populated responses with normalization + pagination fixes.

## Execution outcomes (2026-04-01)

- Hockey Reference parser dedup now prefers stable key sources in order: player href id (e.g. `mcdavid01`) → `data-append-csv` → name fallback.
- Added regression test to ensure same-name players with distinct HR ids are not incorrectly deduped in a single season.
- Targeted tests passed:
  - `pytest tests/scrapers/test_hockey_reference.py -v` → 31 passed
  - `pytest tests/scrapers/test_nhl_com.py tests/scrapers/test_nst.py -v` → 85 passed
- One-season data-quality verification passed (`2024-25`):
  - `total=925`, `gp_rows=924`, `rate_rows=914` (`98.9%`), `raw_rows=920` (`99.6%`)
  - No validation failures; TOI non-negativity check passed.

## Merge outcome (2026-04-01)

- PR #30 merged successfully into `main`.
- Canonical status now advances from scraper/backfill closeout into draft-kit workflow/UI scope lock.
