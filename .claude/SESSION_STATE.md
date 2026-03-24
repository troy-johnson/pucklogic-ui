# Session State

| Field | Value |
|---|---|
| Active Phase | Phase 3e — First Real Training Run |
| Active Branch | main (feat/phase3d-model-training open as PR #28) |
| Open PR | #28 — feat/phase3d-model-training |
| Current Focus | Phase 3d complete; 3e (first real training run) is next after PR #28 merges |
| Last Action | Resolved 3 post-review issues on PR #28 (commit 87a2d0a): holdout metrics validity, scraper backfill --history flag, .gitignore path. 790 tests passing. |
| Session Tier | — |
| Spec | `docs/superpowers/specs/2026-03-23-phase3d-model-training.md` |
| Plan | `docs/superpowers/plans/2026-03-23-phase3d-model-training.md` |
| Next Steps | 1. Merge PR #28  2. Phase 3e: first real training run (see checklist below)  3. Phase 3f: inference API (GET /trends) |

## Phase 3e — First Real Training Run Checklist

Prerequisites (manual, before any code):
- [ ] PR #28 merged
- [ ] `ml-artifacts` Storage bucket created in Supabase dashboard (public: false)
- [ ] `.env` confirmed with real `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `CURRENT_SEASON=2026-27`

Steps:
- [ ] `python -m scrapers.hockey_reference --history` — backfill 2008-09 → current season into `player_stats`
- [ ] Spot-check `player_stats`: verify `sh_pct_career_avg`, `nhl_experience`, `career_goals` non-null for a known player
- [ ] `python -m ml.train --season 2026-27` — full training run (~10–30 min with Optuna)
- [ ] Verify Supabase Storage: `ml-artifacts/2025-26/` contains `breakout_model.joblib`, `regression_model.joblib`, `metadata.json`
- [ ] Inspect `metadata.json`: confirm `n_train > 0`, `n_holdout > 0`, AUC-ROC values present
- [ ] Verify `player_trends` table: rows exist for `season="2025-26"` with non-null `breakout_score`, `regression_risk`, `shap_top3`
- [ ] Sanity-check top 10 breakout scores — values should be in (0, 1), SHAP top3 should list recognizable feature names

Gate for Phase 3f: `player_trends` must be non-empty before the inference API is worth building.

## Phase 3d Design Decisions (do not re-litigate)

- `_HOLDOUT_SEASONS = {2023, 2024}` — excluded from CV, included in final retrain
- Holdout metrics in metadata.json come from a **pre-retrain model** (trained on X_train only) — valid out-of-sample estimates
- Feature window: `data_season="2025-26"` → `current_season_int_val=2026` → window `(2026, 2025, 2024)`
- SHAP label: `compute_shap(..., label="breakout")` and `compute_shap(..., label="regression")` — distinct keys
- Loader upsert: `file_options={"upsert": "true"}` on all 3 Storage uploads (re-runnable)
- Loader type guard: `isinstance(model, xgb.XGBClassifier)` after both dev cache and Storage download
- Annual retrain workflow: `python -m scrapers.hockey_reference --history` then `python -m ml.train --season "$CURRENT_SEASON"`
- LightGBM challenger only — no artifact uploaded; WARNING if LGB AUC > XGB AUC by >0.02

## Phase 3d Post-Merge TODOs

- Update `apps/api/CLAUDE.md` Phase 3d status rows to ✅ Complete
- Close Phase 3d Notion card
