# Adversarial PR/QA Review — Plan 013 VORP Export Column

**Reviewer:** Claude Sonnet 4.6 (adversarial mode)  
**Date:** 2026-05-16  
**Files reviewed:**  
- `apps/api/services/exports.py`  
- `apps/api/tests/services/test_exports.py`  
- `apps/api/routers/exports.py`  
- `apps/api/models/schemas.py`  
- `apps/web/src/app/(auth)/dashboard/page.tsx`  
- `apps/web/src/components/PreDraftWorkspace.tsx`  
- `apps/web/src/components/SourceWeightSelector.tsx`  
- `apps/web/src/lib/api/exports.ts`  
- `apps/web/src/lib/rankings/load-initial.ts`  
- `apps/web/src/store/slices/sources.ts`  
- `docs/specs/012-export-polish.md`  
- `docs/specs/013-vorp-export-column.md`

---

**Verdict:** APPROVED WITH NITS

The backend Spec 013 implementation is correct for the VORP column behavior, and the `is None` guard is correctly applied in every backend location reviewed. The follow-up commit resolved all three review findings: first-load exports now fall back to initial source weights instead of submitting an empty `source_weights` map, the PDF null-VORP data-cell assertion exists, and `_NOTES` is defined at module scope. Focused backend and frontend verification passed.

---

## Blockers (must fix before merge)

None.

### Resolved B-1 — First-load exports can submit empty `source_weights`, causing 422 instead of a download

`loadInitialRankings` computes equal source weights for the initial rankings request, but it returns only `sources`, `rankings`, `season`, `scoringConfigId`, and `platform`. It does not return the computed `sourceWeights`.

`dashboard/page.tsx` passes `initialSources`, `initialRankings`, and `exportContext` to `PreDraftWorkspace`, but it does not hydrate the Zustand source slice.

`PreDraftWorkspace` displays `initialSources` when the store has no sources, but export submission uses `weights` directly from `useStore()`:

```tsx
const { sources, weights, setWeight, resetWeights } = useStore();
...
sourceWeights: weights,
```

The source store defaults to `sources: []` and `weights: {}`. Therefore, on the normal first-load path, a user can click either export button and send an API body with:

```json
"source_weights": {}
```

`ExportRequest.source_weights_not_all_zero` rejects an empty map with a validation error (`source_weights: at least one source must have a non-zero weight`), producing a 422. The frontend categorizes that as `missing-context` and displays "Complete or recompute your kit before exporting." instead of downloading the XLSX/PDF.

This violates the user-facing export behavior from Spec 012:

- AC1 — export rankings as XLSX from the pre-draft workspace
- AC2 — export draft sheet as PDF from the pre-draft workspace
- AC5 — missing-context messaging is reserved for true missing kit/context, not a valid first-load state with sources and rankings already present

**Resolution:** Fixed in follow-up commit `9988b6923a63ec4ab403d859fa4755d182e66141`. `loadInitialRankings` now returns `sourceWeights`, `dashboard/page.tsx` passes them as `initialWeights`, and `PreDraftWorkspace` uses store weights when populated or falls back to `initialWeights` on first load. Regression coverage added in `PreDraftWorkspace.test.tsx`: `uses initialWeights when store weights are empty on first load`.

---

## Important Findings (should fix)

None.

### Resolved I-1 — AC10 bullet 3 not implemented: "Null VORP → '—' in PDF table cell" test is absent

AC10 lists nine bullets under "New tests cover". Bullet 3 is:

> Null VORP → "—" in PDF table cell (backend service test)

No such test exists. The two PDF tests that set `vorp: None` — `test_pdf_vorp_header_has_asterisk_when_null_vorp` and `test_pdf_footnote_present_when_null_vorp` — assert the header asterisk and the footnote text respectively. Neither asserts that the player data row in the HTML contains `"—"` for the VORP cell.

The spec simultaneously marks AC4 as "pre-satisfied, no implementation needed", but then lists this test as a required deliverable under AC10. The spec is internally inconsistent on this point. Regardless: the implementation at line 282 of `exports.py` does render `"—"` for null VORP in the PDF row (`f"<td class='num'>{round(vorp, 1) if vorp is not None else '—'}</td>"`), and that behavior is correct. It is simply not exercised by a dedicated assertion.

**Resolution:** Fixed in follow-up commit `9988b6923a63ec4ab403d859fa4755d182e66141`. `test_pdf_null_vorp_renders_em_dash_in_data_cell` now asserts `<td class='num'>—</td>` for a PDF row with null VORP.

---

## Minor Findings (optional)

### Resolved M-1 — `_NOTES` defined as a function-local constant in `generate_excel`

`_NOTES` (lines 178–190 of `exports.py`) is an immutable list of string literals that never changes between calls. It is defined inside `generate_excel`, meaning Python reconstructs it on every call. The underscore prefix conventionally signals a module-level private constant.

**Resolution:** Fixed in follow-up commit `9988b6923a63ec4ab403d859fa4755d182e66141`. `_NOTES` now lives at module scope alongside `_HEADERS` and `_POSITION_ORDER`.

### M-2 — Spec AC10 says "7 new tests added" but lists 8 backend test bullets

The AC10 preamble says "7 new tests added" while the bullet list contains 8 backend service tests (the ninth bullet — "Frontend: no frontend label changes required" — is a note, not a test). This is a spec documentation error. The implementation now delivers all 8 backend service tests after the I-1 follow-up. The remaining issue is documentation-only and does not block merge.

---

## AC Coverage Summary

### Spec 013 — VORP export column

| AC | Status | Evidence |
|----|--------|----------|
| AC1 — `_HEADERS[5]` = "Value Over Replacement" | PASS | `exports.py` line 21; both sheet writers use `_HEADERS` via `ws.append(_HEADERS)` |
| AC2 — PDF `<th>` shows "Value Over Replacement" | PASS | `_HTML_TEMPLATE` uses `{vorp_header}` placeholder; `vorp_header` set to `"Value Over Replacement"` or `"Value Over Replacement*"` |
| AC3 — Null VORP → "—" in both XLSX sheets; 0.0 not affected | PASS | `vorp if vorp is not None else "—"` at lines 65 and 126; `is None` predicate correct; XLSX tests pass with real openpyxl |
| AC4 — Null VORP → "—" in PDF data cell | PASS | Line 283 renders `"—"` correctly; `test_pdf_null_vorp_renders_em_dash_in_data_cell` asserts `<td class='num'>—</td>` for null VORP. |
| AC5 — PDF asterisk when any VORP null; none when empty list | PASS | `has_null_vorp = any(r.get("vorp") is None for r in rankings)` at line 261; `any([])` is `False` by Python spec; test coverage: `test_pdf_vorp_header_has_asterisk_when_null_vorp` and `test_pdf_no_asterisk_or_footnote_when_empty_rankings` |
| AC6 — PDF footnote when any VORP null; absent otherwise | PASS | Lines 263–268; footnote string matches spec exactly; test coverage: `test_pdf_footnote_present_when_null_vorp` and `test_pdf_no_asterisk_or_footnote_when_all_vorp_present` |
| AC7 — XLSX Notes tab as third sheet, three canonical rows | PASS | `wb.create_sheet(title="Notes")` at line 177; all three strings match spec exactly (verified by string comparison); test: `test_notes_sheet_is_third_tab_with_canonical_glossary` |
| AC8 — `_HEADERS` shared; rename fixes both sheets automatically | PASS | Both `_write_rankings_sheet` and `_write_by_position_sheet` call `ws.append(_HEADERS)`; single constant at line 14 |
| AC9 — No frontend changes | PASS | No changes outside `apps/api/`; column labels are backend-generated strings |
| AC10 — Test renames and new tests | PASS | Both method renames confirmed (`test_header_row_has_value_over_replacement`, `test_html_contains_value_over_replacement`); no stale "Projected Fantasy Value" strings anywhere; all 8 required backend service tests are present, including `test_pdf_null_vorp_renders_em_dash_in_data_cell`. |

### Spec 012 regression check — export download path

| AC | Status | Evidence |
|----|--------|----------|
| AC1 — XLSX export downloads from pre-draft workspace | PASS | `loadInitialRankings` returns `sourceWeights`, `dashboard/page.tsx` passes `initialWeights`, and `PreDraftWorkspace` falls back to `initialWeights` when store weights are empty. Regression test covers first-load empty-store export. |
| AC2 — PDF export downloads from pre-draft workspace | PASS | Same `initialWeights` fallback applies to `draft-sheet` PDF export. |
| AC5 — Export error messaging distinguishes missing context | PASS | Empty store weights no longer force the first-load path into a validation-driven missing-context message when initial weights are available. |

---

## Ship Gate Assessment

**Ship gate:** READY

Reason: B-1, I-1, and M-1 are resolved. The only remaining item is M-2, a non-blocking documentation count mismatch in the plan/spec language.

---

## Additional Observations

**0.0 VORP edge case — no dedicated test, but not a blocker.** The `RANKINGS` fixture uses `vorp: 50.0` and `vorp: 30.0`. `test_pdf_no_asterisk_or_footnote_when_all_vorp_present` exercises the non-null path and would catch a falsy-check regression (because `50.0` is truthy). However, there is no test with `vorp: 0.0` that proves the em-dash is NOT rendered. This is a gap the spec called out in the implementation notes ("VORP of 0.0 is a valid replacement-level value and must not render as '—'") but did not mandate as an explicit test case. The `is None` predicate in the implementation is correct and sufficient. Adding a `vorp: 0.0` test would be belt-and-suspenders hardening against future accidental regression.

**Ruff:** All checks pass. No E501 or other violations in either file.

**Test execution:** 45/45 pass in 0.60 s. `services/exports.py` has 100% line coverage.

**Em-dash character:** All `"—"` literals in both files are confirmed U+2014 (not en-dash U+2013 or hyphen-minus U+002D).

**Footnote string:** Exact match to spec — `"* Configure a league profile for this kit in your PuckLogic dashboard to unlock Value Over Replacement rankings."` — confirmed by character-level comparison.
