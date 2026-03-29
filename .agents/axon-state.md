| Field | Value |
|---|---|
| Active Phase | Scraper data quality hardening and historical backfill verification completed for production-ready coverage targets; next execution track is Hockey Reference dedup closure + first real ML run |
| Active Branch | feat/scraper-data-quality |
| Open PR | None |
| Current Focus | Execute first real ML run using corrected historical NST/NHL data now that Hockey Reference traded-player/career dedup logic is implemented and tested |
| Last Action | Attempted HR verification backfill + first real ML run; HR verification hit source-side 403 and ML run is blocked locally by Python 3.14 incompatibility with SHAP/numba (training runtime expects Python 3.11–3.13) |
| Pending External | Legal/commercial review of third-party aggregated data usage before monetized extension launch |
| Current Hypothesis | With corrected historical backfills (NHL raw from 2005-06 onward, NST per-60 from 2007-08 onward), the first real ML execution run can proceed once Hockey Reference dedup is closed |
| Next Steps | 1. Re-run HR-targeted backfill verification window 2. Execute first real ML run + sanity review 3. Lock draft kit workflow/UI scope |

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

## Current execution blockers

- Hockey Reference verification rerun currently blocked by source-side `403 Forbidden` on season pages in this runtime environment.
- `python -m ml.train --season 2026-27` is blocked locally because `shap` pulls `numba` which does not support Python 3.14; run training in a Python 3.11–3.13 environment.
