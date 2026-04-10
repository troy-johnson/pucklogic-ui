# Draft Season Readiness Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` when implementing this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PuckLogic draft-season ready by shipping a stable web draft kit first: projection aggregation, fantasy-point output, auth + saved kits, and spreadsheet/export workflow. Treat the paid in-draft extension as a secondary launch only if it does not jeopardize the web product.

**Why this plan exists:** The project currently has stronger backend/data progress than product/UI progress. Most UI is still unbuilt or undecided, extension work has not started, and the first real ML backfill/train/validation run has not happened. The highest-value near-term work is to stabilize the data foundation and then finish the draft kit workflow users will actually rely on in draft season.

**Time remaining:** ~24 weeks from 2026-03-28 to mid-September draft season

**Recommended launch strategy:**
1. **Primary launch (late Aug / early Sep):** web draft kit
2. **Secondary launch (Sep / Oct):** paid extension MVP/beta, only if it does not jeopardize the web product

**Current branch reality:** active work is `feat/scraper-data-quality` — NHL/NST hardening, HR dedup, first ML execution, and trends API hardening are complete; PR #30 is open and awaiting review.

---

## Reasoning Behind the Plan

### 1. Data correctness is the dependency under everything else
Rankings, fantasy-point output, exports, ML features, and extension suggestions all depend on trustworthy historical data. Shipping UI on top of bad data would create misleading output faster.

### 2. The core product is the draft kit workflow
The launchable user journey is:
1. configure league/scoring
2. aggregate projections
3. output fantasy-point rankings
4. save kits/account state
5. export/download a usable draft sheet
6. optionally use the extension during the draft

### 3. UI/product completeness is now a larger risk than backend planning
Backend/data/spec planning is relatively advanced. The bigger unknown is whether the actual user journey is defined and built well enough to ship.

### 4. Extension work is risky, but still within reach
The extension involves platform adapters, draft-room DOM variability, auth/session/payment integration, and real-time UX. It should not block the web launch, but it remains a realistic stretch target if scope stays tight.

### 5. ML should prove value quickly or stop blocking progress
There is substantial ML planning, but no real backfill → train → validate cycle yet. Best case, trends clearly improve the draft kit; fallback case, functioning + sane outputs are acceptable for launch.

### 6. Aggregation remains the primary draft-season value proposition
The product should continue to emphasize projection aggregation and fantasy-point output during draft season, including the eventual role of PuckLogic’s own projections.

---

## Already Built (Repo Reality)

### Phase 2 backend — already complete
- [x] Rankings compute backend
- [x] Projections repository/service path
- [x] Cache service
- [x] Export service (Excel + PDF)
- [x] Stripe checkout/webhook backend
- [x] Auth router
- [x] Players router
- [x] User kits backend
- [x] Custom upload backend
- [x] Schedule scores backend
- [x] Platform positions backend

### Phase 3c — already complete in code
- [x] Hockey Reference scraper
- [x] Elite Prospects scraper
- [x] NHL EDGE scraper
- [x] `PlayerStatsRepository`
- [x] `services/feature_engineering.py`

### Phase 3d — already complete in code
- [x] `ml/train.py`
- [x] `ml/loader.py`
- [x] `ml/evaluate.py`
- [x] `ml/shap_compute.py`
- [x] `GET /trends`
- [x] Retraining GitHub Action
- [x] FastAPI startup model loader

### Hits/blocks prerequisite code — complete, rollout still pending
- [x] Migration 005 is written
- [x] NHL.com and NST scraper changes are written
- [x] Feature engineering updates are written
- [x] ML feature list updates are written

### Biggest unfinished areas (post-PR30)
- [ ] Review/merge PR #30 on the current branch
- [ ] frontend draft kit UI
- [ ] browser extension implementation
- [ ] legal/commercial review of third-party data usage at monetized draft-time surfaces

---

## Launch Objective

### Must ship by draft season
- [ ] Trustworthy stat/projection data for launch-critical workflows
- [ ] Web draft kit workflow
- [ ] Fantasy-point rankings output
- [ ] Auth + saved kits
- [ ] Spreadsheet/downloadable draft sheet
- [ ] Usable desktop-first UI

### Nice to ship by draft season
- [ ] ML trends overlay, if validated
- [ ] Extension MVP, if capacity allows

### Explicit non-goals for the critical path
- [ ] Do **not** make the extension a hard blocker for the September launch
- [ ] Do **not** broaden the launch UI beyond the core draft kit flow

---

## Current Status by Phase

### Phase 1 — Foundation & Data Pipeline
**Status:** mostly complete  
**What’s true now:** no longer the main strategic blocker, but unresolved scraper correctness still affects launch readiness.

### Phase 2 — Aggregation Dashboard / Draft Kit
**Status:** backend complete, frontend workflow incomplete  
**What’s true now:** the backend path for aggregation/scoring/export/auth exists; the actual draft kit UI still needs definition and implementation.

### Phase 3a — Scrapers & Expanded Data Sources
**Status:** implemented enough to proceed, still being hardened  
**What’s true now:** feature-complete-ish, but not yet fully trusted operationally.

### Phase 3b — Smoke Test / Verification
**Status:** framework exists, launch-confidence still being earned  
**What’s true now:** “complete” procedurally, but still dependent on current data-quality work.

### Phase 3c — Feature Engineering
**Status:** code-complete, not yet validated by a real ML execution cycle  
**What’s true now:** feature pipeline exists and is ahead of UI/extension work.

### Phase 3d / 3e / 3f — Model Training / Inference / Retraining
**Status:** code-complete, not yet executed/validated on real launch data  
**What’s true now:** not speculative anymore; the remaining gap is real-world execution and product validation.

### Phase 4 — Extension
**Status:** not started  
**What’s true now:** risky, but still within reach if web UI scope stays tight and ESPN-first MVP is acceptable.

---

## Milestone Timeline

| Milestone | Window | Duration | Notes |
|---|---|---:|---|
| A — Close scraper hardening + backfill | Mar 28 – Apr 12 | 2 weeks | includes migration/backfill prerequisites |
| F — First real ML execution run | Apr 13 – Apr 20 | 1 week | execution-focused, not architecture work |
| B — Lock draft kit workflow / UI scope | Apr 21 – May 4 | 2 weeks | defines the launch UI/product shape |
| C — Verify + gap-fill backend integration | May 5 – May 18 | 2 weeks | backend is mostly complete |
| D — Build web draft kit UI | May 19 – Jun 29 | 6 weeks | only realistic if scope stays narrow |
| E — Polish exports | Jun 30 – Jul 13 | 2 weeks | draft-day usability focus |
| G — Launch hardening | Jul 14 – Aug 17 | 5 weeks | stabilization buffer |
| H — Extension go/no-go | Aug 18 – Aug 24 | 1 week | decide whether MVP fits |
| I — Extension MVP / beta | Aug 25 – Sep 14 | 3 weeks | ESPN-first if both platforms do not fit |

---

## Milestone Plan

## Milestone A — Close scraper hardening + backfill
**Window:** 2026-03-28 → 2026-04-12

**Why this comes first:** all rankings, exports, ML, and extension suggestions depend on it.

- [ ] Finish Hockey Reference multi-team/career dedup
- [ ] Finish current scraper hardening branch work
- [x] Apply migration 005 in Supabase
- [x] Run `python -m scrapers.nst --history`
- [x] Run `python -m scrapers.nhl_com --history`
- [x] Verify launch-critical fields for rankings/output/export/ML
- [ ] Document trusted data baseline

**Done means:**
- [ ] No known critical scraper correctness bugs remain
- [x] Historical backfill is verified for launch-critical stats (NHL raw from `2005-06+`, NST rates from `2007-08+`)
- [x] Data-quality verification steps are repeatable and documented
- [ ] The dataset is trusted enough to support the first real ML execution run

**Launch gate A:** Do not move to product build work unless the data baseline is trusted.

## Milestone F — First real ML execution run
**Window:** 2026-04-13 → 2026-04-20

**Why here:** the ML code path already exists; delaying the first real execution would waste iteration time.

- [ ] Run training successfully on real data
- [ ] Produce artifacts and confirm they load correctly
- [ ] Verify `GET /trends` works against real artifacts/data
- [ ] Review outputs for sanity
- [ ] Decide whether trends are clearly useful, or whether “functioning + sane outputs” is the acceptable launch baseline

**Done means:**
- [ ] First real ML run completed
- [ ] Artifacts produced and loadable
- [ ] Trends path works against real data
- [ ] Outputs are sane enough to continue product integration
- [ ] Explicit ML launch decision documented

**Launch gate F:** ML is no longer speculative; it is either validated or explicitly scoped as a fallback-quality launch feature.

## Milestone B — Lock the draft kit workflow / UI scope
**Window:** 2026-04-21 → 2026-05-04

**Why this comes next:** product ambiguity is a bigger risk than code volume.

- [ ] Define exact launch user flow from setup → rankings → saved kits → export
- [ ] Define supported scoring/league workflows at launch
- [ ] Define required screens/routes/components
- [ ] Define must-have vs post-launch features
- [ ] Confirm extension is not a blocker for September launch

**Done means:**
- [ ] One agreed v1 workflow exists
- [ ] One agreed must-have feature list exists
- [ ] One agreed cut list exists
- [ ] The 6-week UI build is feasible under the approved scope

**Launch gate B:** No major UI/product ambiguity remains.

## Milestone C — Verify + gap-fill backend integration
**Window:** 2026-05-05 → 2026-05-18

**Why this comes before frontend implementation:** UI should build on stable contracts and stable output shape.

- [ ] Verify scoring config path against real draft kit workflows
- [ ] Verify aggregation output shape and edge cases
- [ ] Verify fantasy-point output path
- [ ] Verify auth + saved kits requirements end-to-end
- [ ] Ensure export uses the same canonical output pipeline
- [ ] Fix remaining blocker-level backend integration gaps for frontend work

**Done means:**
- [ ] A user can produce rankings/fantasy-point output from valid inputs
- [ ] Auth + saved kits path is ready for UI integration
- [ ] Export data path is coherent with rankings path
- [ ] No blocker-level backend gaps remain for UI implementation

**Launch gate C:** Backend supports the real product workflow end-to-end.

## Milestone D — Build the web draft kit UI
**Window:** 2026-05-19 → 2026-06-29

**Why this is the main build phase:** this is the actual product most users will touch.

**Important assumption:** this 6-week window is only realistic if the launch UI stays desktop-first and narrow.

- [ ] Build league/scoring setup UI
- [ ] Build source weighting / kit configuration UI
- [ ] Build rankings/results UI
- [ ] Build auth + saved kits UI
- [ ] Build export/download UI
- [ ] Dogfood the full user workflow internally

**Done means:**
- [ ] A real user can go from setup → rankings → saved kits → export
- [ ] Core desktop UX is usable without manual workarounds
- [ ] Product is internally dogfoodable

**Launch gate D:** The web draft kit exists as a coherent, usable workflow.

## Milestone E — Make exports launch-grade
**Window:** 2026-06-30 → 2026-07-13

**Why this matters:** export can still carry launch value even if extension slips.

- [ ] Polish spreadsheet structure
- [ ] Validate readability during a live draft
- [ ] Test Excel/Google Sheets compatibility
- [ ] Ensure output includes the right fantasy-point/ranking fields
- [ ] Ensure printable/downloadable draft flow is usable

**Done means:**
- [ ] Export is genuinely useful during a real draft
- [ ] No embarrassing formatting/data issues remain
- [ ] Export can stand alone as a fallback draft-day product

**Launch gate E:** Spreadsheet/download flow is launch-worthy.

## Milestone G — Harden the web launch
**Window:** 2026-07-14 → 2026-08-17

**Why this matters:** this is the final stabilization buffer before draft season pressure.

- [ ] Fix critical workflow bugs
- [ ] Polish top-priority UI/UX issues
- [ ] Verify export and rankings stability
- [ ] Verify auth/payment basics
- [ ] Run end-to-end checks on the core journey
- [ ] Review legal/commercial implications of third-party aggregated data in the monetized product path

**Done means:**
- [ ] No critical defects in the core web workflow
- [ ] Rankings, exports, and draft prep flows are stable
- [ ] Product is safe to put in front of real users
- [ ] Launch packaging is not carrying unresolved legal/commercial surprises

**Launch gate G:** Web draft kit is launch-ready.

## Milestone H — Extension go/no-go
**Window:** 2026-08-18 → 2026-08-24

**Why this checkpoint exists:** to prevent the extension from derailing a ready web product.

- [ ] Assess whether the web product is stable
- [ ] Assess remaining engineering capacity
- [ ] Decide whether extension MVP is feasible for September
- [ ] Decide whether both platforms fit or whether MVP should be ESPN-first

**Done means:**
- [ ] Explicit decision: proceed or defer
- [ ] If proceeding, MVP scope is tightly constrained
- [ ] Platform scope is explicit

**Launch gate H:** Extension only proceeds if the web launch is already safe.

## Milestone I — Extension MVP / beta (conditional)
**Window:** 2026-08-25 → 2026-09-14

**Why this is conditional:** highest-risk, least-started workstream.

- [ ] Implement ESPN-first if both platforms do not fit
- [ ] Implement pick detection
- [ ] Implement top-available suggestions
- [ ] Implement minimal session/auth/payment gating
- [ ] Provide manual fallback if automation fails

**Done means:**
- [ ] Real users can complete a draft with it, or
- [ ] It is explicitly deferred without affecting the web product launch

---

## Priority Order

### Tier 1 — non-negotiable
- [ ] scraper hardening
- [ ] backfill verification
- [ ] draft kit workflow definition
- [ ] fantasy-point rankings flow
- [ ] auth + saved kits
- [ ] usable web UI
- [ ] spreadsheet/export product

### Tier 2 — important, but should not block launch
- [ ] first real ML execution run
- [ ] trends UI if validated
- [ ] launch hardening

### Tier 3 — stretch
- [ ] extension MVP
- [ ] multi-platform extension support at launch

---

## Cut Rules If Behind

### If behind by mid-May
- [ ] cut nonessential UI complexity
- [ ] narrow configuration surface
- [ ] focus only on the core workflow
- [ ] do **not** cut auth + saved kits

### If behind by late June
- [ ] treat export as primary draft-day product
- [ ] simplify rankings UI before adding breadth

### If behind by late July
- [ ] make ML optional or lower-visibility
- [ ] do not let ML block the draft kit

### If behind by late August
- [ ] defer one-platform extension MVP if needed
- [ ] launch web draft kit only

---

## Final Launch Recommendation

The highest-probability draft-season success path is:

- ship the web draft kit first
- make exports strong enough to be useful during drafts
- keep auth + saved kits as required scope
- let ML ship if it is either clearly useful or at least functioning + sane
- let the extension ship only if it does not endanger the web launch

This gives PuckLogic the best chance of having a genuinely usable product by mid-September instead of a partially finished all-at-once launch.
