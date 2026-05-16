# Adversarial PR/QA Review — Milestone E Export Polish (Round 2)

**Artifact type:** Implementation review  
**Spec:** `docs/specs/012-export-polish.md`  
**Plans:** `docs/plans/012a-export-polish-backend.md`, `docs/plans/012b-export-polish-frontend.md`  
**Round number:** 2  
**Prior review:** `docs/specs/012-export-polish-adversarial-pr-review-r1.md`  
**Reviewer lens:** Spec compliance, blocker resolution, end-to-end wiring, test evidence  
**Required verdict set:** `APPROVED`, `APPROVED WITH NITS`, `HOLD`  
**Review date:** 2026-05-13

---

## Files Reviewed

- `apps/api/routers/exports.py`
- `apps/api/services/exports.py`
- `apps/api/tests/routers/test_exports.py`
- `apps/api/tests/services/test_exports.py`
- `apps/web/src/app/(auth)/dashboard/__tests__/page.test.tsx`
- `apps/web/src/app/(auth)/dashboard/page.tsx`
- `apps/web/src/components/PreDraftWorkspace.tsx`
- `apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx`
- `apps/web/src/lib/api/__tests__/exports.test.ts`
- `apps/web/src/lib/api/__tests__/index.test.ts`
- `apps/web/src/lib/api/exports.ts`
- `apps/web/src/lib/api/index.ts`
- `apps/web/src/lib/rankings/load-initial.ts`

---

## Blocker Resolution Status

### B-1 — `exportContext` never passed to `PreDraftWorkspace`

**RESOLVED.**

`apps/web/src/app/(auth)/dashboard/page.tsx` now destructures `season`, `scoringConfigId`, and `platform` from `loadInitialRankings` and passes them to `PreDraftWorkspace` as `exportContext`. The prop is conditionally set: if `scoringConfigId` is null (no presets loaded), `exportContext` is `undefined`, which correctly routes the user to the "Complete or recompute your kit" message on export click. The `token` from the session is forwarded, preserving auth.

Wiring path: `supabase.auth.getSession()` → `token` → `loadInitialRankings(token)` → `{ scoringConfigId, season, platform }` → `exportContext={...}`. All three required values are present in the happy path.

New test in `apps/web/src/app/(auth)/dashboard/__tests__/page.test.tsx` asserts that `PreDraftWorkspace` receives `exportContext` with `token`, `season`, `scoringConfigId`, and `platform` matching the mocked `loadInitialRankings` return.

### B-2 — `generate_excel`/`generate_pdf` missing concrete scoring context

**RESOLVED.**

Both functions now accept a `context_label: str | None = None` parameter. The router builds a rich `context_label` via `_build_export_context_label` containing: scoring config name + ID, league profile name, and a sorted source-weight summary. This label is passed to both generators and rendered as:

- XLSX: `wb.properties.title` (workbook title) and `wb.properties.subject` (full context label)
- PDF: `<p class="context">` elements for season, league context, and generated timestamp

The router resolves `sc_row.get("name") or req.scoring_config_id` for the config name, ensuring the label never falls back to a bare ID when a human-readable name is available.

### B-3 — Test suites not verified

**RESOLVED.**

Both suites pass cleanly:

- Backend (`tests/services/test_exports.py` + `tests/routers/test_exports.py`): **62 passed in 0.63s**. `services/exports.py` achieves **100% statement coverage**. `routers/exports.py` achieves **98% coverage**.
- Frontend (`pnpm test`): **202 passed across 27 test files**.

---

## Stage 1 — Spec Compliance

| AC | Status | Evidence |
|----|--------|----------|
| AC1 | PASS | `PreDraftWorkspace.handleExport("rankings")` calls `downloadExport({ type: "rankings", ... })` → `apiFetchBinary("/exports/generate", { export_type: "excel" })` → `triggerBrowserDownload` with `.xlsx` blob. Confirmed by `exports.test.ts` and `PreDraftWorkspace.test.tsx`. |
| AC2 | PASS | Same path with `type: "draft-sheet"` → `export_type: "pdf"` → `.pdf` blob. Both paths covered by test. |
| AC3 | PASS | `if (exporting === type) return` prevents duplicate submissions per-action. Button is `disabled={exporting === type}` and label changes to "Exporting rankings/draft sheet…". Tested with deferred-promise pattern. |
| AC4 | PASS | Backend: `_export_filename` produces `pucklogic-{sanitized-config-id}-{rankings|draft-sheet}-{YYYY-MM-DD}.{ext}`. Frontend: `filenameFromResponse` reads `Content-Disposition`, falling back to `fallbackFilename` using the same deterministic pattern. Router test pins `_export_date` and asserts exact filename string. |
| AC5 | PASS | Four distinct messages: "Sign in to export your draft kit." / "Export requires an active kit pass." / "Complete or recompute your kit before exporting." / "Export failed. Try again." Each tested in `PreDraftWorkspace.test.tsx`. |
| AC6 | PASS | Previously unwired export buttons are now onClick-wired with `disabled` during loading. No dead buttons remain. |
| AC7 | PASS | `_HEADERS` list contains `["Rank", "Player", "Position", "Team", "PuckLogic Score", "Projected Fantasy Value", "OffNightGames", "Source Count", ...]`. Workbook `title` and `subject` carry rich scoring/league/source context. `test_launch_xlsx_minimum_columns_and_context_metadata` asserts first six columns and workbook metadata. |
| AC8 | PASS | PDF template includes: title "PuckLogic Draft Sheet", season, league context label, generated timestamp, and player rows with Rank/Player/Team/Pos/PuckLogic Score/Projected Fantasy Value/Off-Night columns. `test_printable_draft_sheet_header_context_and_timestamp` asserts all fields. |
| AC9 | PASS | `_HEADERS` is a module-level constant; column order is stable. `test_header_row_first_four_columns` and `test_launch_xlsx_minimum_columns_and_context_metadata` assert fixed column positions. |
| AC10 | PASS | PDF title "PuckLogic Draft Sheet" and header row are stable constants in `_HTML_TEMPLATE`. `test_printable_draft_sheet_uses_passed_context_label` inspects rendered HTML string via `mock_module.HTML.call_args.kwargs["string"]`. |
| AC11 | PASS | `ExportRequest.export_type` uses `Field(..., pattern="^(pdf|excel)$")`. Pydantic rejects `"csv"` and unsupported types with 422. `test_csv_export_type_does_not_invoke_generation` verifies neither generator is called. |
| AC12 | PASS | `require_kit_pass` dependency retained on `generate_export`. `TestKitPassGating.test_generate_export_returns_403_when_user_lacks_active_kit_pass` confirmed. |
| AC13 | PASS | Source ownership check (wrong user_id → 400), paid-source subscription check (is_paid + no sub → 403), scoring config existence check (None → 404), league profile authorization check (None → 403) all present and tested in `TestExportAccessValidation`. |
| AC14 | PASS | Backend tests use `MagicMock` for all repos and mock `generate_excel`/`generate_pdf` in router tests; `weasyprint` patched via `sys.modules`. Frontend mocks `fetch` via `vi.spyOn`. No real DB, payment, or external calls. |
| AC15 | PASS | **62 backend tests passed. 202 frontend tests passed.** Zero failures. |

**Stage 1 verdict: PASS**

---

## Stage 2 — Code Quality

No new blockers.

### Important

**I-1: Column label semantics — confirm with product owner before launch**

`apps/api/services/exports.py` maps `projected_fantasy_points` → "PuckLogic Score" column, `vorp` → "Projected Fantasy Value" column. `projected_fantasy_points` is the scoring-config-weighted fantasy point total and is the primary ranking driver — calling it "PuckLogic Score" is defensible. However, `vorp` ("Projected Fantasy Value") will be `None` for any export not using a league profile, rendering this column blank for most users. The labeling and null behavior should be confirmed by the product owner before launch. Not a spec violation, but a user-facing semantic question.

### Minor

**M-1: `create=True` on `_export_date` patch is unnecessary**

`apps/api/tests/routers/test_exports.py` uses `patch("routers.exports._export_date", return_value="2026-05-11", create=True)` in three tests. `create=True` is only needed when patching an attribute that doesn't exist; `_export_date` is a defined function. Omitting it provides a safety net: if the function is renamed, the test raises `AttributeError` immediately instead of silently creating an unused attribute.

**M-2: Untested path — `source_weights` key absent from `get_by_names` return (router line ~84)**

Coverage reports one uncovered line: the `raise HTTPException(400, f"Unknown source key: {key}")` branch when a `source_weights` key is entirely absent from the DB lookup. No test sends a key that doesn't exist at all in `get_by_names`. Reachable from a malicious or stale client.

**M-3: No test for `PreDraftWorkspace` rendered without `exportContext`**

When `exportContext` is `undefined`, `handleExport` shows the missing-context message directly without calling `downloadExport`. Existing tests always pass `EXPORT_CONTEXT`. The code path at `PreDraftWorkspace.tsx` ~line 92–94 is untested from the component's own test file (the dashboard page test covers the prop-wiring side, not the component's behavior when prop is absent).

**M-4: Cross-format column order inconsistency (XLSX vs PDF)**

XLSX header order: `Rank, Player, Position, Team, ...`. PDF header order: `Rank, Player, Team, Pos, ...`. Team and Position/Pos are swapped between formats, and PDF abbreviates "Position" as "Pos". AC9 and AC10 are per-format, so this does not violate the spec. However, users comparing both exports will see different column layouts. Low severity, worth future alignment.

**M-5: 403 from league-profile ownership error falls through to `"generation-failed"`**

`categoryForApiError` maps 403 to `"no-pass"` only when the message contains "kit pass". A 403 from "Not authorized to access this league profile" falls through to `"generation-failed"`, surfacing "Export failed. Try again." rather than the more actionable "Complete or recompute your kit". Rare in normal usage but a UX gap.

### Carried from Round 1 (deferred nits — still open)

**M-6 (was M-1):** `filenameFromResponse` regex doesn't handle RFC 5987 `filename*=UTF-8''...`. Backend generates ASCII-safe names so this is not a current regression risk.

**M-7 (was M-2):** `fallbackFilename` date uses client clock (`new Date().toISOString().slice(0, 10)`); backend filenames use UTC. One-day drift possible near midnight for UTC+ users.

---

## Ship Gate Assessment

| Gate requirement | Status |
|---|---|
| B-1 resolved | PASS |
| B-2 resolved | PASS |
| B-3 resolved | PASS |
| AC1–AC6 frontend behavior | PASS |
| AC7–AC10 backend content | PASS |
| AC11–AC13 gating/regressions | PASS |
| AC14 no live-service calls | PASS |
| AC15 tests pass | PASS (62 backend, 202 frontend) |

**Ship gate: CLEAR**

---

## Verdict

`APPROVED WITH NITS`

All three prior blockers are resolved. All 15 acceptance criteria are met. No regressions in existing tests. Four nits recommended for follow-up:

1. **(Important — I-1)** Confirm with product owner that "Projected Fantasy Value" = VORP (blank for most exports) is intentional before launch.
2. **(M-1)** Remove `create=True` from the three `_export_date` patch calls in `test_exports.py`.
3. **(M-2)** Add a router test providing a `source_weights` key absent from `get_by_names` return.
4. **(M-3)** Add a `PreDraftWorkspace` test that renders without `exportContext` and clicks an export button, asserting the missing-context message.

None of these block merge for a launch milestone.
