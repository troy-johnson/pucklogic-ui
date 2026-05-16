# Adversarial PR/QA Review — Plan 013 VORP Export Column

**Reviewer:** Claude Sonnet 4.6 (adversarial mode)  
**Date:** 2026-05-16  
**Files reviewed:**  
- `apps/api/services/exports.py`  
- `apps/api/tests/services/test_exports.py`  
- `docs/specs/013-vorp-export-column.md`

---

**Verdict:** APPROVED WITH NITS

The implementation is correct and complete for all user-facing behavior. All 45 tests pass, ruff is clean, and the `is None` guard is correctly applied in every location. Two findings follow: one important (a missing test that AC10 explicitly requires), one minor (a style nit on constant scoping).

---

## Blockers (must fix before merge)

None.

---

## Important Findings (should fix)

### I-1 — AC10 bullet 3 not implemented: "Null VORP → '—' in PDF table cell" test is absent

AC10 lists nine bullets under "New tests cover". Bullet 3 is:

> Null VORP → "—" in PDF table cell (backend service test)

No such test exists. The two PDF tests that set `vorp: None` — `test_pdf_vorp_header_has_asterisk_when_null_vorp` and `test_pdf_footnote_present_when_null_vorp` — assert the header asterisk and the footnote text respectively. Neither asserts that the player data row in the HTML contains `"—"` for the VORP cell.

The spec simultaneously marks AC4 as "pre-satisfied, no implementation needed", but then lists this test as a required deliverable under AC10. The spec is internally inconsistent on this point. Regardless: the implementation at line 282 of `exports.py` does render `"—"` for null VORP in the PDF row (`f"<td class='num'>{round(vorp, 1) if vorp is not None else '—'}</td>"`), and that behavior is correct. It is simply not exercised by a dedicated assertion.

The gap is a test coverage omission, not an implementation bug. However, AC10 is explicit: this test should exist.

Suggested fix — add to `TestGeneratePdf`:

```python
def test_pdf_null_vorp_renders_em_dash_in_data_cell(self) -> None:
    rankings = [{**PLAYER_A, "vorp": None}]
    html = _capture_html(rankings, SEASON)
    # The data row should contain em-dash for the VORP cell, not blank or "None"
    assert "<td class='num'>—</td>" in html
```

---

## Minor Findings (optional)

### M-1 — `_NOTES` defined as a function-local constant in `generate_excel`

`_NOTES` (lines 178–190 of `exports.py`) is an immutable list of string literals that never changes between calls. It is defined inside `generate_excel`, meaning Python reconstructs it on every call. The underscore prefix conventionally signals a module-level private constant.

This is not a correctness issue, has no observable performance impact for this workload, and ruff does not flag it. It is a style inconsistency with `_HEADERS` and `_POSITION_ORDER`, which are module-level. Consider moving `_NOTES` to module scope alongside the other constants.

### M-2 — Spec AC10 says "7 new tests added" but lists 8 backend test bullets

The AC10 preamble says "7 new tests added" while the bullet list contains 8 backend service tests (the ninth bullet — "Frontend: no frontend label changes required" — is a note, not a test). This is a spec documentation error. The implementation delivers 7 of those 8 (missing bullet 3 per I-1 above). The discrepancy in the spec itself should be corrected in a future spec revision; it created ambiguity that may have caused the implementer to miscount and omit the PDF cell test.

---

## AC Coverage Summary

| AC | Status | Evidence |
|----|--------|----------|
| AC1 — `_HEADERS[5]` = "Value Over Replacement" | PASS | `exports.py` line 21; both sheet writers use `_HEADERS` via `ws.append(_HEADERS)` |
| AC2 — PDF `<th>` shows "Value Over Replacement" | PASS | `_HTML_TEMPLATE` uses `{vorp_header}` placeholder; `vorp_header` set to `"Value Over Replacement"` or `"Value Over Replacement*"` |
| AC3 — Null VORP → "—" in both XLSX sheets; 0.0 not affected | PASS | `vorp if vorp is not None else "—"` at lines 65 and 126; `is None` predicate correct; XLSX tests pass with real openpyxl |
| AC4 — Null VORP → "—" in PDF data cell | PASS (impl), PARTIAL (test) | Line 282 renders `"—"` correctly; but AC10 bullet 3 test is absent — see I-1 |
| AC5 — PDF asterisk when any VORP null; none when empty list | PASS | `has_null_vorp = any(r.get("vorp") is None for r in rankings)` at line 261; `any([])` is `False` by Python spec; test coverage: `test_pdf_vorp_header_has_asterisk_when_null_vorp` and `test_pdf_no_asterisk_or_footnote_when_empty_rankings` |
| AC6 — PDF footnote when any VORP null; absent otherwise | PASS | Lines 263–268; footnote string matches spec exactly; test coverage: `test_pdf_footnote_present_when_null_vorp` and `test_pdf_no_asterisk_or_footnote_when_all_vorp_present` |
| AC7 — XLSX Notes tab as third sheet, three canonical rows | PASS | `wb.create_sheet(title="Notes")` at line 177; all three strings match spec exactly (verified by string comparison); test: `test_notes_sheet_is_third_tab_with_canonical_glossary` |
| AC8 — `_HEADERS` shared; rename fixes both sheets automatically | PASS | Both `_write_rankings_sheet` and `_write_by_position_sheet` call `ws.append(_HEADERS)`; single constant at line 14 |
| AC9 — No frontend changes | PASS | No changes outside `apps/api/`; column labels are backend-generated strings |
| AC10 — Test renames and new tests | PARTIAL | Both method renames confirmed (`test_header_row_has_value_over_replacement`, `test_html_contains_value_over_replacement`); no stale "Projected Fantasy Value" strings anywhere; 7 of 8 required backend tests present; AC10 bullet 3 absent — see I-1 |

---

## Additional Observations

**0.0 VORP edge case — no dedicated test, but not a blocker.** The `RANKINGS` fixture uses `vorp: 50.0` and `vorp: 30.0`. `test_pdf_no_asterisk_or_footnote_when_all_vorp_present` exercises the non-null path and would catch a falsy-check regression (because `50.0` is truthy). However, there is no test with `vorp: 0.0` that proves the em-dash is NOT rendered. This is a gap the spec called out in the implementation notes ("VORP of 0.0 is a valid replacement-level value and must not render as '—'") but did not mandate as an explicit test case. The `is None` predicate in the implementation is correct and sufficient. Adding a `vorp: 0.0` test would be belt-and-suspenders hardening against future accidental regression.

**Ruff:** All checks pass. No E501 or other violations in either file.

**Test execution:** 45/45 pass in 0.60 s. `services/exports.py` has 100% line coverage.

**Em-dash character:** All `"—"` literals in both files are confirmed U+2014 (not en-dash U+2013 or hyphen-minus U+002D).

**Footnote string:** Exact match to spec — `"* Configure a league profile for this kit in your PuckLogic dashboard to unlock Value Over Replacement rankings."` — confirmed by character-level comparison.
