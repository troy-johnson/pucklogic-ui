# Draft Season Readiness Plan — Revision 1

> Review-only revision for another model. This file captures the requested changes to `008a-draft-season-readiness.md` without rewriting the main plan yet.

## Requested changes

1. Remove 1 week from Milestone D (web draft kit UI).
2. Pull all later milestones up by 1 week.
3. Treat the extension as still reachable, not a likely deferral.
4. Make the plan reflect that the UI should not require 6–7 weeks of pure build time.

## Revision rationale

- Backend work is farther along than the current plan implies, so the long “backend completion” window should be shortened.
- The first real ML run should happen much earlier because the code path already exists; what remains is execution on real data.
- The extension should keep a real launch window because the remaining schedule is still workable if web UI scope stays tight.

## Updated milestone timeline

| Milestone | New Window | Duration | Notes |
|---|---|---:|---|
| A — Close scraper hardening + backfill | Mar 28 – Apr 12 | 2 weeks | unchanged |
| F — First real ML run | Apr 13 – Apr 20 | 1 week | pulled forward from July; execution-focused |
| B — Lock draft kit workflow / UI scope | Apr 21 – May 4 | 2 weeks | pulled up 1 week |
| C — Verify + gap-fill backend integration | May 5 – May 18 | 2 weeks | pulled up 1 week; backend is mostly complete |
| D — Build web draft kit UI | May 19 – Jun 29 | 6 weeks | trimmed by 1 week from the prior 7-week window |
| E — Polish exports | Jun 30 – Jul 13 | 2 weeks | pulled up 1 week |
| G — Launch hardening | Jul 14 – Aug 17 | 5 weeks | pulled up 1 week; extra buffer remains |
| H — Extension go/no-go | Aug 18 – Aug 24 | 1 week | pulled up 1 week |
| I — Extension MVP / beta | Aug 25 – Sep 14 | 3 weeks | pulled up 1 week; still feasible if scope stays small |

## Scope adjustments implied by this revision

### Milestone C
Rename from “Complete draft kit backend path” to **“Verify + gap-fill backend integration”**.

Reason: the backend is already substantially built, so this phase should focus on contract verification, integration gaps, and product-path sanity checks rather than new greenfield implementation.

### Milestone D
Keep it as the web UI build window, but reduce it to **6 weeks**.

Reason: the UI is still the largest product gap, but the surrounding backend is complete enough that the build should be scoped tightly and executed aggressively.

### Milestone F
Move the first real ML cycle to **April**.

Reason: the ML code path already exists; the remaining work is validation on real data. Delaying that test until late summer would waste iteration time.

## Planning notes for the review model

- The updated plan should explicitly note that **Phase 2 backend is already complete**.
- It should also distinguish between **code-complete** and **real-world executed/validated** for ML.
- The web draft kit remains the main launch objective.
- The extension is not the primary launch blocker, but it remains in reach and should retain a realistic MVP window.

## Open questions for review

1. Is the 6-week UI window realistic given the backend is already done?
2. Is an April ML validation run early enough, or should it move even earlier?
3. Does the 3-week extension MVP window remain acceptable if the web product stays on track?
4. Are there additional scope cuts needed to preserve the mid-September deadline?
