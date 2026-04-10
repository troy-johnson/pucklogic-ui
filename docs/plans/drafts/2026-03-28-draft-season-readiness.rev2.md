# Draft Season Readiness Plan — Revision 2

> Review-only revision for another model. This file incorporates review feedback on `2026-03-28-draft-season-readiness.rev1.md` without rewriting the main readiness plan yet.

## What changed from Revision 1

1. Added an explicit **Already built (repo reality)** section so the schedule starts from what is actually complete.
2. Clarified that **Phase 3d is code-complete** and that the remaining work is execution/validation on real data.
3. Added explicit **manual prerequisites** before the first real ML run.
4. Added a stronger warning that the **6-week UI window only works if scope is tightly constrained**.
5. Kept the revised timeline from Revision 1: 1 week removed from UI, all later milestones pulled up by 1 week, extension still in reach.

---

## Requested changes carried forward

1. Remove 1 week from Milestone D (web draft kit UI).
2. Pull all later milestones up by 1 week.
3. Treat the extension as still reachable, not a likely deferral.
4. Make the plan reflect that the UI should not require 6–7 weeks of pure build time.

---

## Revision rationale

- Backend work is farther along than the original plan implied, so the long “backend completion” window should be shortened.
- The first real ML run should happen much earlier because the code path already exists; what remains is execution on real data plus a small set of manual rollout steps.
- The extension should keep a real launch window because the remaining schedule is still workable if web UI scope stays tight.
- The final plan should distinguish between **code complete** and **executed/validated in a real environment**.

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

---

## Updated milestone timeline

| Milestone | New Window | Duration | Notes |
|---|---|---:|---|
| A — Close scraper hardening + backfill | Mar 28 – Apr 12 | 2 weeks | unchanged |
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

### Milestone C
Rename from “Complete draft kit backend path” to **“Verify + gap-fill backend integration”**.

Reason: the backend is already substantially built, so this phase should focus on contract verification, integration gaps, and product-path sanity checks rather than greenfield implementation.

### Milestone D
Keep it as the web UI build window, but reduce it to **6 weeks**.

Reason: the UI is still the largest product gap, but the surrounding backend is complete enough that the build should be scoped tightly and executed aggressively.

**Important assumption:** this 6-week window is only realistic if Milestone B locks the launch scope tightly and keeps the UI desktop-first and narrow:
- setup/config flow
- rankings/results table
- export/download path
- minimal account/kit persistence as needed

It is **not** realistic if the project tries to ship a broad dashboard surface or significant optional UI work in the same window.

### Milestone F
Move the first real ML cycle to **April**.

Reason: the ML code path already exists; the remaining work is validation on real data. Delaying that test until late summer would waste iteration time.

**Manual prerequisites before Milestone F:**
1. Apply migration 005 in Supabase
2. Run `python -m scrapers.nst --history`
3. Run `python -m scrapers.nhl_com --history`
4. Confirm scraper hardening work from Milestone A is complete enough to trust the resulting dataset

**Clarification:** Phase 3d is **code-complete** in the repo. Milestone F is about **real-world execution and validation**, not major new ML implementation.

---

## Planning notes for the review model

- The updated plan should explicitly note that **Phase 2 backend is already complete**.
- It should explicitly distinguish between **code-complete** and **real-world executed/validated** for ML.
- The web draft kit remains the main launch objective.
- The extension is not the primary launch blocker, but it remains in reach and should retain a realistic MVP window.
- The 6-week UI window is acceptable only if scope is aggressively constrained during Milestone B.

---

## Open questions for review

1. Is the 6-week UI window realistic given the backend is already done and scope is aggressively constrained?
2. Is an April ML execution run early enough, or should it move even earlier?
3. Does the 3-week extension MVP window remain acceptable if the web product stays on track?
4. Are there any additional scope cuts needed to preserve the mid-September deadline?
5. Should the final merged readiness plan include a second ML checkpoint in July/August for iteration after the first execution run?
