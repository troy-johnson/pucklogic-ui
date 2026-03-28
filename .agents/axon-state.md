| Field | Value |
|---|---|
| Active Phase | Draft season readiness plan approved; scraper data quality hardening + backfill verification remains the active execution track |
| Active Branch | feat/scraper-data-quality |
| Open PR | None |
| Current Focus | Main readiness plan updated from rev3; current engineering work remains NHL.com, NST, and Hockey Reference scraper fixes plus backfill/data-quality verification before the first real ML execution run |
| Last Action | Promoted the approved draft season readiness plan to `docs/superpowers/plans/2026-03-28-draft-season-readiness.md`, archived prior drafts, and synced planning/state docs toward `.agents/axon-state.md` |
| Pending External | Legal/commercial review of third-party aggregated data usage before monetized extension launch |
| Current Hypothesis | Once Hockey Reference dedup, migration 005, and history backfills are complete, the project can run the first real ML execution cycle in April and then shift to locking the draft kit UI scope |
| Next Steps | 1. Finish Hockey Reference multi-team/career dedup 2. Run targeted scraper tests 3. Apply migration 005 and run NST/NHL.com history backfills 4. Execute the first real ML run 5. Lock draft kit workflow/UI scope |

## Scraper data quality status

- Phase 1 (NHL.com) complete on `feat/scraper-data-quality`
- Verified with `pytest tests/scrapers/test_nhl_com.py -v` → 29 passed
- Smoke fixture updated for `NhlComScraper.scrape()` returning `(summary_count, realtime_count)`
- `psycopg2-binary` installed locally so `tests/smoke/conftest.py` imports cleanly in this environment
- Phase 2 (NST) complete on `feat/scraper-data-quality`
- Verified with `pytest tests/scrapers/test_nst.py -v` → 46 passed

## Phase 1 decisions now in force

- NHL.com summary and realtime URLs use `isAggregate=true`
- For traded players, `players.team` stores the last team from comma-joined `teamAbbrevs`
- NHL.com realtime pass falls back to `players.nhl_id` lookup before skipping missing summary-map players
- NHL.com realtime logging reports separate summary and realtime counts
- `realtime_count` only increments when hits/blocks were actually written

## Phase 2 decisions now in force

- NST parser supports both legacy and current hits/blocks per-60 headers (`iHF/60` / `Hits/60`, `iBLK/60` / `Shots Blocked/60`)
- NST TOI parsing prefers explicit `TOI/GP` when present, otherwise derives per-game TOI from total `TOI / GP`
- `toi_sh` should now reflect actual short-handed TOI/game instead of inheriting all-situations TOI/game

## Approved planning direction now in force

- The web draft kit is the primary launch target for draft season; the extension remains a secondary launch that must not block the web product
- Auth + saved kits are required launch scope for the web product
- The first real ML run should happen immediately after data hardening/backfill work is complete
- ESPN-first is the acceptable fallback for extension MVP scope if both ESPN and Yahoo do not fit
