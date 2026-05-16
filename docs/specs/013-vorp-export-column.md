# 013 — VORP Export Column

**Status:** Approved — adversarial spec review r1 complete; pre-plan gate met  
**Date:** 2026-05-13  
**Track:** Express  
**Related research:** `docs/research/006-vorp-export-column-brainstorm.md`  
**Related specs:** `docs/specs/012-export-polish.md`  
**Triggered by:** Adversarial review I-1 from `docs/specs/012-export-polish-adversarial-pr-review-r2.md`

---

## Summary

Rename the "Projected Fantasy Value" export column to "Value Over Replacement", render null VORP as an em dash ("—") instead of a blank cell, and add a conversion nudge in both XLSX (Notes tab) and PDF (asterisk + footnote) directing users without a league profile to configure one in their dashboard.

VORP remains in the export. The blank column for non-league users becomes an explicit product signal, not a silent gap.

---

## Goals

- Replace the misleading "Projected Fantasy Value" label with the technically accurate "Value Over Replacement".
- Eliminate silent blank cells by rendering null VORP as "—".
- Use the null state as a growth moment: nudge users toward configuring a league profile.
- Keep the nudge copy future-proof by using prose only (no hardcoded URL).

## Non-Goals

- Populating VORP with a fallback value when null.
- Suppressing the column when VORP is unavailable.
- Changing any other column label or data mapping.
- Adding any new entitlement or paywall logic.
- Changing the league profile setup flow itself.

---

## Acceptance Criteria

### AC1 — Column label renamed in XLSX

The "Projected Fantasy Value" header in XLSX output is replaced with "Value Over Replacement". All other column labels and positions are unchanged.

### AC2 — Column label renamed in PDF

The "Projected Fantasy Value" column header in PDF output is replaced with "Value Over Replacement". All other column labels and positions are unchanged.

### AC3 — Null VORP renders as "—" in both XLSX sheets

When a player's `vorp` value is `None`, the corresponding cell contains the string `"—"` (U+2014, em dash) rather than an empty cell or `None`. This applies to both the Full Rankings sheet and the By Position sheet, each of which has an independent row writer.

### AC4 — Null VORP renders as "—" in PDF

When a player's `vorp` value is `None`, the corresponding PDF table cell contains `"—"` (U+2014, em dash) rather than blank content.

### AC5 — PDF column header carries an asterisk when VORP is null for any player

When at least one player in the export has a null `vorp`, the "Value Over Replacement" PDF column header is rendered as "Value Over Replacement*".

When all players have non-null VORP (league profile configured), the header is rendered as "Value Over Replacement" with no asterisk.

When the rankings list is empty, no asterisk is rendered.

Rationale: The asterisk links the column header visually to the footnote. The condition is evaluated as `any(r.get("vorp") is None for r in rankings)`. Use `is None` (not a falsy check) — VORP of `0.0` is a valid replacement-level value and must not trigger the asterisk.

### AC6 — PDF footnote present when VORP is null for any player

When at least one player has a null `vorp`, a footnote appears below the player table in the PDF:

> `"* Configure a league profile for this kit in your PuckLogic dashboard to unlock Value Over Replacement rankings."`

The footnote is italicized and visually distinct from the player table rows. When the rankings list is empty or all players have non-null VORP, no footnote is rendered. Same `is None` predicate as AC5.

### AC7 — XLSX Notes tab present in every export

Every XLSX workbook includes a sheet named "Notes" appended as the third tab, after "By Position". The Notes sheet uses a single-column layout: one glossary entry per row in column A, plain text, no formatting.

The three required rows, in order:

1. `"PuckLogic Score: The scoring-configuration-weighted fantasy point projection for this player."`
2. `"Value Over Replacement (VORP): Measures a player's projected fantasy value relative to the replacement-level player at their position in your league. Configure a league profile for this kit in your PuckLogic dashboard to unlock this column."`
3. `"Source Count: The number of ranking sources that include this player."`

The Notes sheet must not contain player data rows or interfere with the primary data sheets.

### AC8 — Column order and all other XLSX columns unchanged

`_HEADERS` contains "Value Over Replacement" at the same index previously occupied by "Projected Fantasy Value". No other header is added, removed, or reordered.

### AC9 — Column order and all other PDF columns unchanged

The PDF template renders "Value Over Replacement" (or "Value Over Replacement*") at the same position previously occupied by "Projected Fantasy Value". No other column is affected.

### AC10 — Tests updated and passing

All existing tests that assert the string "Projected Fantasy Value" are updated to "Value Over Replacement". The two test methods whose names encode the old label (`test_header_row_has_projected_fantasy_value`, `test_html_contains_projected_fantasy_value`) are renamed to match.

New tests cover:

- Null VORP → "—" in Full Rankings XLSX sheet cell (backend service test)
- Null VORP → "—" in By Position XLSX sheet cell (backend service test)
- Null VORP → "—" in PDF table cell (backend service test)
- PDF asterisk on column header when at least one VORP null (backend service test)
- PDF footnote present when at least one VORP null (backend service test)
- PDF asterisk and footnote absent when all VORP non-null (backend service test); the existing `RANKINGS` fixture covers this case
- PDF asterisk and footnote absent when rankings list is empty (backend service test)
- XLSX Notes tab present as third sheet with exact canonical glossary strings (backend service test)
- Frontend: no frontend label changes required (column labels are backend-generated)

Both `pytest` (backend) and `pnpm test` (frontend) must pass with zero failures.

---

## Out of Scope

| Item | Disposition |
|---|---|
| VORP fallback to `projected_fantasy_points` | Rejected — produces two identical columns for most users |
| Suppress column when VORP unavailable | Rejected — violates AC9 (stable column count) from spec 012 |
| `composite_score` as replacement for VORP | Deferred — future column-roster review |
| Hardcoded URL in nudge copy | Rejected — exported files are permanent; URLs go stale |
| Changing "PuckLogic Score" label | Out of scope for this spec |

---

## Implementation Notes

- `_HEADERS` in `apps/api/services/exports.py`: replace `"Projected Fantasy Value"` with `"Value Over Replacement"`.
- XLSX row writers: guard `vorp` in **both** `_write_rankings_sheet` and `_write_by_position_sheet` with `value if value is not None else "—"`. Use `is None` — VORP of `0.0` is a valid replacement-level value and must not render as `"—"`.
- PDF template: replace the column header string; guard the cell value the same way; conditionally append `"*"` to the header and render the footnote `<p>` based on `any(r.get("vorp") is None for r in rankings)`.
- Notes tab: `workbook.create_sheet("Notes")` (no position arg, appends as third tab); write the three canonical glossary strings as plain cell values in column A, one per row.
- AC5/AC6 predicate: `has_null_vorp = any(r.get("vorp") is None for r in rankings)`. Pass as a parameter to `generate_pdf` or derive inside it.
