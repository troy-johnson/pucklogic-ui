| Field | Value |
|---|---|
| Active Phase | Scraper data quality hardening and historical backfill verification completed for production-ready coverage targets; next execution track is Hockey Reference dedup closure + first real ML run |
| Active Branch | feat/scraper-data-quality |
| Open PR | #30 — https://github.com/troy-johnson/pucklogic-ui/pull/30 |
| Current Focus | Await PR #30 review/merge after completing scraper hardening, HR dedup, first real ML run, and trends API stability fixes |
| Last Action | Completed HR verification backfill, executed first real ML run (artifacts + player_trends writes), fixed trends position validation + pagination, and opened PR #30 |
| Pending External | Legal/commercial review of third-party aggregated data usage before monetized extension launch |
| Current Hypothesis | With corrected historical backfills (NHL raw from 2005-06 onward, NST per-60 from 2007-08 onward), the first real ML execution run can proceed once Hockey Reference dedup is closed |
| Next Steps | 1. Address PR #30 review feedback 2. Merge scraper hardening/ML closeout branch 3. Move to draft kit workflow/UI lock |

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
