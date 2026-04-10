| Field | Value |
|---|---|
| Active Phase | Milestone B locked — wireframe design decisions captured; design system and implementation planning next |
| Active Branch | feat/live-draft-sync-spec |
| Open PR | None |
| Current Focus | Completing Milestone B design artifacts before Milestone D (web UI build, May 19) — design system section of spec 010 is the remaining open item |
| Last Action | Approved spec 009, closed all Milestone B decisions (kit pass $4.99, draft passes $2.99 separate, Discord beta feedback pipeline), wrote wireframe design spec 010 |
| Pending External | Legal/commercial review of third-party aggregated data usage before monetized extension launch |
| Current Hypothesis | Layout decisions are locked; design system (colors, typography, tokens) needs to be defined before Milestone D implementation planning can begin |
| Next Steps | 1. Complete design system section of spec 010 2. Write Milestone C implementation plan (backend verification, May 5–18) 3. Write Milestone D implementation plan (web UI build, May 19–Jun 29) |

## Documentation continuity outcome (2026-04-07)

- `docs/specs/009-web-draft-kit-ux.md` is the canonical Milestone B web-first UX contract.
- Supporting brainstorm material now lives in `docs/research/002-web-draft-kit-ux-brainstorm.md`.
- Durable architecture decisions now live under `docs/adrs/`, including `007-web-first-draft-session-and-temp-kit-lifecycle.md`.
- Research docs now use their own numbered sequence with `docs/research/INDEX.md` as the folder guide.
- `docs/README.md` now documents folder classification, canonical-source precedence, numbering policy, and the requirement to keep `.agents/axon-state.md` current when docs meaningfully change.

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
