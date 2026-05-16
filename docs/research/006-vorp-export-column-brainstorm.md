# Brainstorm — VORP Export Column Treatment (Post-Milestone-E Nit I-1)

**Artifact type:** Brainstorm  
**Date:** 2026-05-13  
**Trigger:** Adversarial review I-1 — "Projected Fantasy Value" column shows VORP which is null for users without a league profile  
**Outcome:** Express track approved; scope resolved

---

## Problem

The XLSX and PDF exports contain a column labeled "Projected Fantasy Value" whose value is `vorp` — a stat that is `None` for any user who has not configured a league profile. Most users fall into this category. The label implies an absolute fantasy points projection rather than a relative differential, and the blank column provides no signal or guidance.

---

## Key Constraint

VORP is a well-known stat among savvy fantasy users and must remain in the export. Removing it is not an option. The blank column for non-league users is a **growth opportunity**, not a defect to hide.

---

## Design Decisions

### 1. Column label

**Decision:** Rename "Projected Fantasy Value" → **"Value Over Replacement"**.

Rationale: Target users know the stat. "Projected Fantasy Value" incorrectly implies an absolute projection. "Value Over Replacement" is precise and self-explanatory to the audience.

Alternatives considered and rejected:
- "VORP" — too terse for users unfamiliar with the acronym; "Value Over Replacement" is no longer and clearer
- Keep "Projected Fantasy Value" — misleading label, implies raw points

### 2. Null cell treatment

**Decision:** Render `None` as **"—"** (em dash) in both XLSX cells and PDF cells.

Rationale: Explicit absence is better than an empty cell. "—" is a standard convention for "not applicable" in stat tables.

### 3. Conversion nudge — XLSX

**Decision:** Add a **Notes tab** to the workbook.

Content: A plain-text sheet with one note per column that has nuance, including:
> "Value Over Replacement (VORP): Configure a league profile for this kit in your PuckLogic dashboard to unlock Value Over Replacement rankings."

Rationale:
- A trailing note row below data breaks downstream imports
- Workbook metadata (subject/description) is low-visibility — most users never open it
- A Notes tab is discoverable, doesn't interfere with data rows, and is a standard spreadsheet pattern for column glossaries

### 4. Conversion nudge — PDF

**Decision:** Add an **asterisk to the "Value Over Replacement" column header** and a **footnote below the player table**.

Footnote text:
> "* Configure a league profile for this kit in your PuckLogic dashboard to unlock Value Over Replacement rankings."

Rationale: Footnotes are a natural PDF convention. The asterisk creates a visual link between the blank column and the explanation.

### 5. CTA URL

**Decision:** **No URL** — prose only.

Rationale: Exported files are permanent artifacts. A hardcoded URL becomes stale if the settings flow moves. The target users (savvy fantasy players) can navigate back to the app without hand-holding. Prose-only copy is future-proof.

---

## Out of Scope

- Populating VORP with a fallback value when null — rejected (would make "PuckLogic Score" and "Value Over Replacement" identical for most users)
- Suppressing the column when null — rejected (violates stable column order AC9 and removes a product signal)
- Using `composite_score` in place of VORP — deferred; valid for a future column-roster review, not this nit

---

## Resolved Scope (Express Track)

1. Rename `"Projected Fantasy Value"` → `"Value Over Replacement"` in `_HEADERS` and PDF template
2. Render `None` VORP as `"—"` in XLSX row writer and PDF row template
3. Add asterisk to PDF VORP column header; add footnote below player table
4. Add Notes tab to XLSX workbook with column glossary and VORP conversion nudge
5. Update all affected tests
