# Draft Season Readiness Plan — Revision 3

> Review-only revision for another model. This file incorporates follow-up decisions from review of `008a-draft-season-readiness.rev2.md` without rewriting the main readiness plan yet.

## Decisions carried into this revision

1. **Milestone A should explicitly include the migration/backfill steps** that make the first real ML run possible.
2. **Extension MVP may target one platform first** if both ESPN and Yahoo do not fit; prefer **ESPN first**.
3. **Auth + saved kits are required for the web launch** and are not optional scope cuts.
4. **ML launch bar:** ideal outcome is that trends clearly improve the draft kit, but **functioning + sane outputs** is an acceptable fallback for launch.
5. The product should continue to emphasize the **aggregation feature during draft season**, including the eventual role of PuckLogic’s own projections.

---

## What changed from Revision 2

1. Moved migration/backfill steps into **Milestone A** as part of the data-foundation exit criteria.
2. Clarified that **Milestone F** is not just “run ML” — it must produce artifacts, power the trends path, and be reviewed for sanity/usefulness.
3. Added the explicit assumption that **auth + saved kits are required launch scope**.
4. Added **ESPN-first** as the preferred fallback for the extension MVP.
5. Added a **legal/commercial review risk** around third-party data usage, especially if the extension is monetized while surfacing aggregated external data.

---

## Revision rationale

- Backend work is farther along than the original plan implied, so the long “backend completion” window should be shortened.
- The first real ML run should happen much earlier because the code path already exists; what remains is execution on real data plus manual rollout steps.
- The extension should keep a real launch window because the remaining schedule is still workable if web UI scope stays tight.
- Auth and saved kits are part of the product promise and should not be treated as optional frontend polish.
- The aggregation feature is still the core draft-season value proposition, including the future use of PuckLogic’s own projections.

---

## Already built (repo reality)

The updated readiness plan should start from this baseline:

### Phase 2 backend — already complete
- Rankings compute backend
- Projections repository/service path
- Cache service
- Export service (Excel + PDF)
- Stripe checkout/webhook backend
- Auth router
- Players router
- User kits backend
- Custom upload backend
- Schedule scores backend
- Platform positions backend

### Phase 3c — already complete in code
- Hockey Reference scraper
- Elite Prospects scraper
- NHL EDGE scraper
- `PlayerStatsRepository`
- `services/feature_engineering.py`

### Phase 3d — already complete in code
- `ml/train.py`
- `ml/loader.py`
- `ml/evaluate.py`
- `ml/shap_compute.py`
- `GET /trends`
- retraining GitHub Action
- FastAPI startup model loader

### Hits/blocks prerequisite code — complete, rollout still pending
- migration 005 is written
- NHL.com and NST scraper changes are written
- feature engineering updates are written
- ML feature list updates are written

### Biggest unfinished areas
- scraper hardening/backfill verification on the current branch
- frontend draft kit UI
- first real ML execution/validation cycle
- browser extension implementation
- legal/commercial review of third-party data usage at monetized draft-time surfaces

---

## Updated milestone timeline

| Milestone | New Window | Duration | Notes |
|---|---|---:|---|
| A — Close scraper hardening + backfill | Mar 28 – Apr 12 | 2 weeks | includes migration/backfill prerequisites |
| F — First real ML execution run | Apr 13 – Apr 20 | 1 week | pulled forward from July; execution-focused, not architecture work |
| B — Lock draft kit workflow / UI scope | Apr 21 – May 4 | 2 weeks | pulled up 1 week |
| C — Verify + gap-fill backend integration | May 5 – May 18 | 2 weeks | pulled up 1 week; backend is mostly complete |
| D — Build web draft kit UI | May 19 – Jun 29 | 6 weeks | trimmed by 1 week from the prior 7-week window |
| E — Polish exports | Jun 30 – Jul 13 | 2 weeks | pulled up 1 week |
| G — Launch hardening | Jul 14 – Aug 17 | 5 weeks | pulled up 1 week; extra buffer remains |
| H — Extension go/no-go | Aug 18 – Aug 24 | 1 week | pulled up 1 week |
| I — Extension MVP / beta | Aug 25 – Sep 14 | 3 weeks | pulled up 1 week; still feasible if scope stays small |

---

## Scope adjustments implied by this revision

### Milestone A — expanded to include rollout prerequisites
Milestone A should now explicitly include:

1. Finish Hockey Reference multi-team/career dedup
2. Finish current scraper hardening branch work
3. Apply migration 005 in Supabase
4. Run `python -m scrapers.nst --history`
5. Run `python -m scrapers.nhl_com --history`
6. Verify launch-critical fields for rankings/output/export/ML
7. Document trusted data baseline

**Reason:** these are not merely “ML prerequisites” — they are part of closing the data foundation and should be treated as launch-critical data work.

### Milestone C
Rename from “Complete draft kit backend path” to **“Verify + gap-fill backend integration”**.

Reason: the backend is already substantially built, so this phase should focus on contract verification, integration gaps, and product-path sanity checks rather than greenfield implementation.

### Milestone D
Keep it as the web UI build window, but reduce it to **6 weeks**.

Reason: the UI is still the largest product gap, but the surrounding backend is complete enough that the build should be scoped tightly and executed aggressively.

**Important assumptions for the 6-week window:**
- launch UI remains desktop-first
- launch scope remains narrow
- auth + saved kits are **required** and must be included in this window
- setup/config flow, rankings/results table, and export/download path are the core UI

It is **not** realistic if the project tries to ship a broad dashboard surface or significant optional UI work in the same window.

### Milestone F
Move the first real ML cycle to **April**.

Reason: the ML code path already exists; the remaining work is validation on real data. Delaying that test until late summer would waste iteration time.

**Clarification:** Phase 3d is **code-complete** in the repo. Milestone F is about **real-world execution and validation**, not major new ML implementation.

**Milestone F success criteria should include:**
1. Training completes successfully on real data
2. Artifacts are produced and load correctly
3. `GET /trends` works against real artifacts/data
4. Outputs are reviewed for sanity
5. Explicit decision: trends are clearly useful, or “functioning + sane outputs” is acceptable for launch

---

## Extension assumptions

- Extension is still a real stretch target, not just a placeholder.
- If both platforms will not fit, ship **ESPN first**.
- A one-platform MVP is acceptable if:
  - pick detection works reliably enough
  - the paid session flow is workable
  - manual fallback exists
  - the web draft kit remains strong on its own

---

## Product/launch assumptions

### Required for web launch
- auth
- saved kits
- projection aggregation
- fantasy-point rankings
- export/download workflow

### ML launch assumption
Best case: trends measurably improve the draft kit and become a visible differentiator.

Fallback case: trends ship if they are at least **functioning + sane**, even if their product impact is not yet fully proven.

### Aggregation product assumption
The aggregation feature remains the primary draft-season value proposition, including the eventual inclusion of PuckLogic’s own projections.

---

## Legal / commercial risk to review

The final plan should include a short review item for the legality/commercial implications of surfacing third-party aggregated data inside a product that also monetizes draft-time extension usage.

This does **not** necessarily block the readiness plan, but it should become an explicit review track before launch packaging.

Questions to answer later:
1. Are all third-party source ingestion/display patterns acceptable for the web draft kit?
2. Are any additional restrictions needed once the extension becomes paid?
3. Does the inclusion of PuckLogic’s own projections reduce launch/legal exposure over time?

---

## Planning notes for the review model

- The updated plan should explicitly note that **Phase 2 backend is already complete**.
- It should explicitly distinguish between **code-complete** and **real-world executed/validated** for ML.
- The web draft kit remains the main launch objective.
- The extension is not the primary launch blocker, but it remains in reach and should retain a realistic MVP window.
- The 6-week UI window is acceptable only if scope is aggressively constrained during Milestone B.
- Auth + saved kits are required launch scope, not optional extras.

---

## Open questions for review

1. Is the 6-week UI window still realistic once auth + saved kits are treated as required launch scope?
2. Is an April ML execution run early enough, or should it move even earlier?
3. Is ESPN-first the right single-platform fallback for the extension MVP?
4. Are there any additional scope cuts needed to preserve the mid-September deadline?
5. Should the final merged readiness plan include a second ML checkpoint in July/August for iteration after the first execution run?
6. Should the final plan explicitly add a legal/commercial review track before paid extension launch?
