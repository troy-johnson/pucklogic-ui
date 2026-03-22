# Session State

| Field | Value |
|---|---|
| Active Phase | Phase 3d — Model Training Pipeline |
| Active Branch | main |
| Open PR | none |
| Current Focus | Phase 3c complete; Phase 3d next |
| Last Action | PR #26 merged. Phase 3c feature engineering pipeline complete. 727 tests. Codex NO-GO Notion card created. |
| Pending Notion | [3c] Fix NHL.com + MoneyPuck scrapers failing on GitHub Actions (P1, Backlog) |
| Session Tier | — |
| Spec | `docs/superpowers/specs/2026-03-22-phase3c-feature-engineering.md` |
| Plan | `docs/superpowers/plans/2026-03-22-phase3c-feature-engineering.md` |
| Next Steps | 1. Phase 3d: model training pipeline (XGBoost/LightGBM + SHAP + GitHub Action)  2. Before Phase 3d: resolve Codex backlog card (stale_season + position_type flags + spec drift fix) |

## Phase 3c Design Decisions (do not re-litigate)

- D5: No elite finisher whitelist — XGBoost learns from data
- D8: `high_secondary_pct` disabled — `a1` counting stat not in schema
- `age_declining` uses `position in {"C", "LW", "RW"}` (NOT `"F"`) — DB stores NHL.com canonical positions
- `ixg_per60_curr` = current-season raw value for signals; `ixg_per60` = 3-year weighted avg for model features
- `breakout_tier` and `regression_tier` are separate fields; merge to `player_trends.projection_tier` deferred to Phase 3e
- `toi_ev` is stored as per-game rate (NST computes `total_toi / gp`) — `TOI_THRESHOLD = 5.0` min/game is correct
- Stale-season fallback: `rows[0]` used as current when no current-season row exists; warning logged; full retired/minors detection deferred pending `player_status` schema
- Goalies: all scrapers are skater-only (NST/MoneyPuck/NHL.com), so no goalie rows exist in `player_stats` currently; goalie model is Phase 3 backlog

## Phase 3c Known Limitations (tracked in Notion backlog)

- Stale current-season row: retired player detection deferred — needs `player_status` on `players` table
- Goalie projections: separate model required (proposed features in `docs/feature-engineering-spec.md`)
- Feature matrix output contract: `stale_season` and `position_type` flags deferred to before Phase 3d (Notion backlog card created)
- `a2_pct_of_assists` always None (D8); spec testing section needs updating (same Notion card)
