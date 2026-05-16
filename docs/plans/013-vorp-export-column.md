# Plan 013 — VORP Export Column

**Spec:** `docs/specs/013-vorp-export-column.md`  
**Track:** Express  
**Scope:** Backend only — `apps/api/services/exports.py` and `apps/api/tests/services/test_exports.py`  
**Date:** 2026-05-14

**Adversarial plan review:** not required — express track, single-file backend change, no auth/schema/prod-risk triggers.  
**Adversarial PR/QA review:** required before ship-sync.

---

## Pre-implementation notes

From reading `apps/api/services/exports.py`:

- `_HEADERS[5]` is `"Projected Fantasy Value"` — a single rename fixes both XLSX sheets (both call `_write_rankings_sheet` / `_write_by_position_sheet` which use the same `_HEADERS` constant).
- Both XLSX row writers use `_fmt(row.get("vorp"))` — `_fmt(None)` returns `""`, not `"—"`. Both need a targeted null guard.
- `generate_pdf` already renders null VORP as `"—"` in table cells (line 252). AC4 requires no new implementation — only a rename in the column header.
- `_HTML_TEMPLATE` has `<th>Projected Fantasy Value</th>` hardcoded. The asterisk is conditional, so the header must be parameterized via a `{vorp_header}` format slot.
- `generate_excel` creates two sheets (Full Rankings, By Position). The Notes tab is a third `wb.create_sheet("Notes")` append.
- No frontend changes required — column labels are backend-generated.

---

## Task Table

| # | Task | ACs | Wave |
|---|---|---|---|
| 1 | Update existing test assertions: rename test methods and replace all `"Projected Fantasy Value"` strings with `"Value Over Replacement"` | AC1, AC2, AC10 | RED |
| 2 | Add test: null VORP → `"—"` in Full Rankings XLSX cell | AC3, AC10 | RED |
| 3 | Add test: null VORP → `"—"` in By Position XLSX cell | AC3, AC10 | RED |
| 4 | Add test: PDF asterisk on `"Value Over Replacement*"` header when any player has null VORP | AC5, AC10 | RED |
| 5 | Add test: PDF footnote present and contains canonical text when any player has null VORP | AC6, AC10 | RED |
| 6 | Add test: PDF asterisk and footnote absent when all players have non-null VORP | AC5, AC6, AC10 | RED |
| 7 | Add test: PDF asterisk and footnote absent when rankings list is empty | AC5, AC6, AC10 | RED |
| 8 | Add test: XLSX Notes tab is third sheet named `"Notes"` with exact canonical glossary rows | AC7, AC10 | RED |
| 9 | Rename `"Projected Fantasy Value"` → `"Value Over Replacement"` in `_HEADERS` | AC1, AC2, AC8, AC9 | GREEN |
| 10 | Fix `_write_rankings_sheet` row writer: `vorp` cell → `vorp if (vorp := row.get("vorp")) is not None else "—"` | AC3 | GREEN |
| 11 | Fix `_write_by_position_sheet` row writer: same null guard as task 10 | AC3 | GREEN |
| 12 | Parameterize `_HTML_TEMPLATE`: replace `<th>Projected Fantasy Value</th>` with `<th>{vorp_header}</th>`; add `{footnote}` slot after `</table>` | AC2, AC5, AC6 | GREEN |
| 13 | Update `generate_pdf`: compute `has_null_vorp = any(r.get("vorp") is None for r in rankings)`; build `vorp_header` (`"Value Over Replacement*"` or `"Value Over Replacement"`); build `footnote` (`<p class="footnote">...</p>` or `""`); pass both to `_HTML_TEMPLATE.format(...)` | AC5, AC6 | GREEN |
| 14 | Add Notes tab to `generate_excel`: `ws3 = wb.create_sheet(title="Notes")` after By Position; write three canonical glossary rows to column A | AC7 | GREEN |
| 15 | Run `pytest tests/services/test_exports.py tests/routers/test_exports.py -v` — all pass | AC10 | VERIFY |
| 16 | Run `pnpm --filter web test` — 0 failures (regression check; no frontend changes) | AC10 | VERIFY |

---

## Implementation Detail

### Tasks 10–11 — VORP null guard in XLSX row writers

Replace `_fmt(row.get("vorp"))` in both `_write_rankings_sheet` (line 64) and `_write_by_position_sheet` (line 124) with:

```python
row.get("vorp") if row.get("vorp") is not None else "—"
```

Use `is None` — VORP of `0.0` is a valid replacement-level value and must not render as `"—"`.

### Tasks 12–13 — PDF conditional asterisk and footnote

Add two format slots to `_HTML_TEMPLATE`:

```html
<th>{vorp_header}</th>   <!-- replaces <th>Projected Fantasy Value</th> -->
...
</table>
{footnote}
</body>
```

Add footnote CSS class to the style block:

```css
.footnote { color: #475569; font-style: italic; margin-top: 8px; font-size: 10px; }
```

In `generate_pdf`:

```python
has_null_vorp = any(r.get("vorp") is None for r in rankings)
vorp_header = "Value Over Replacement*" if has_null_vorp else "Value Over Replacement"
footnote = (
    "<p class='footnote'>* Configure a league profile for this kit in your PuckLogic "
    "dashboard to unlock Value Over Replacement rankings.</p>"
    if has_null_vorp
    else ""
)
```

### Task 14 — Notes tab

After `ws2 = wb.create_sheet(title="By Position")` in `generate_excel`:

```python
ws3 = wb.create_sheet(title="Notes")
_NOTES = [
    "PuckLogic Score: The scoring-configuration-weighted fantasy point projection for this player.",
    "Value Over Replacement (VORP): Measures a player's projected fantasy value relative to the replacement-level player at their position in your league. Configure a league profile for this kit in your PuckLogic dashboard to unlock this column.",
    "Source Count: The number of ranking sources that include this player.",
]
for note in _NOTES:
    ws3.append([note])
```

---

## Files Changed

| File | Change |
|---|---|
| `apps/api/services/exports.py` | `_HEADERS`, two row writers, `_HTML_TEMPLATE`, `generate_pdf`, `generate_excel` |
| `apps/api/tests/services/test_exports.py` | method renames, assertion updates, 7 new tests |

No other files change. No router changes. No frontend changes. No migration.
