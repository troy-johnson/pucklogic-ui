# Adversarial Spec Review — 013 VORP Export Column

**Artifact type:** Spec review  
**Spec:** `docs/specs/013-vorp-export-column.md`  
**Review date:** 2026-05-13  
**Required verdict set:** `APPROVED`, `APPROVED WITH NITS`, `HOLD`

---

## Summary

Spec 013 is a narrow express-track change: rename one column header, render null VORP as an em dash, add a PDF asterisk/footnote conditional on at least one null VORP, add an XLSX Notes tab, and update tests. The brainstorm artifact is internally consistent with the spec. No blocker issues were found. Two Important issues should be resolved before implementation begins to prevent silent correctness defects and non-deterministic test copy.

---

## Findings

### Blocker

None.

---

### Important

**I-1 — AC3 and AC10 silent on the By Position XLSX sheet**

`services/exports.py` writes VORP in two independent places: `_write_rankings_sheet` and `_write_by_position_sheet`. AC3 says "the corresponding XLSX cell contains '—'" without qualifying which sheet(s). AC10 lists one test — "Null VORP → '—' in XLSX cell (backend service test)" — with no mention of the By Position sheet.

An implementer could fix only `_write_rankings_sheet`, pass the test, and leave the By Position sheet rendering empty strings. This would be a silent correctness defect in the shipped workbook.

**Fix required before planning:** Update AC3 to read "both XLSX sheets (Full Rankings and By Position)". Update AC10 to add: "Null VORP → '—' in By Position sheet cell (backend service test)."

---

**I-2 — AC7 Notes tab content underspecified**

Three issues:

1. No canonical copy is supplied for "PuckLogic Score" or "Source Count" glossary entries. "Brief descriptions" is not enough — two implementers will produce different text. The test in AC10 asserts "expected glossary text" but there is no source of truth for what that text should be.

2. No layout is specified: single-column rows, two-column term/definition layout, bold header row — any of these satisfies the current AC text.

3. The Notes tab sheet position relative to "Full Rankings" and "By Position" is not stated. `workbook.create_sheet("Notes")` without a position argument appends as the third tab (correct), but the spec doesn't commit to this.

**Fix required before planning:** Supply canonical copy for all three glossary entries in AC7. Specify single-column layout (A column, one entry per row). Specify Notes as the third tab (after By Position).

---

### Minor

**M-1 — AC5/AC6 silent on empty rankings list**

`any(r.get("vorp") is None for r in rankings)` returns `False` for an empty list — no asterisk, no footnote — which is correct. But the spec does not state this explicitly. Add one sentence to AC5 or AC6: "When the rankings list is empty, neither asterisk nor footnote is rendered."

**M-2 — Em dash character not formally specified**

AC3 and AC4 show `"—"` but do not name the codepoint. Add a parenthetical: `"—" (U+2014, em dash)`. Protects against copy-paste corruption across editors and distinguishes from en dash or hyphen.

**M-3 — AC10 missing explicit all-non-null XLSX test**

AC10 includes "PDF asterisk and footnote absent when all VORP non-null" but no paired XLSX case. The all-non-null XLSX path is covered implicitly by the renamed-header test using the existing `RANKINGS` fixture. AC10 should acknowledge this explicitly rather than leaving the coverage implicit.

**M-4 — Implementation note should call out `is None` vs. falsy**

VORP of `0.0` is a valid replacement-level value and must not render as `"—"`. The implementation note should read: "Use `is None` (not falsy check) — VORP of 0.0 is a valid replacement-level value."

**M-5 — Test method names encode old label**

Two test methods — `test_header_row_has_projected_fantasy_value` and `test_html_contains_projected_fantasy_value` — should be renamed alongside the assertion strings. AC10's "all existing tests that reference 'Projected Fantasy Value' are updated" covers assertions; the implementation task should explicitly include method renames.

**M-6 — Notes tab position unspecified**

State tab order explicitly in AC7: "The Notes sheet is appended as the third tab, after 'By Position'."

---

## Verdict

`APPROVED WITH NITS`

I-1 and I-2 must be resolved in the spec before planning begins. The Minors can be addressed inline during implementation. No design rework is required — all fixes are additive clarifications to existing ACs.
