# Draft Season Readiness Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` when implementing this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PuckLogic draft-season ready by shipping a stable web draft kit first: projection aggregation, fantasy-point output, and spreadsheet/export workflow. Treat the paid in-draft extension as a secondary launch only if it does not jeopardize the web product.

**Why this plan exists:** The project currently has stronger backend/data progress than product/UI progress. Most UI is still unbuilt or undecided, extension work has not started, and the first real ML backfill/train/validation run has not happened. The highest-value near-term work is to stabilize the data foundation and then finish the draft kit workflow users will actually rely on in draft season.

**Time remaining:** ~24 weeks from 2026-03-28 to mid-September draft season

**Recommended launch strategy:**
1. **Primary launch (late Aug / early Sep):** web draft kit
2. **Secondary launch (Sep / Oct):** paid extension MVP/beta, only if it does not jeopardize the web product

**Current branch reality:** active work is `feat/scraper-data-quality` — scraper hardening + backfill/data-quality verification

---

## Reasoning Behind the Plan

### 1. Data correctness is the dependency under everything else
Rankings, fantasy-point output, exports, ML features, and extension suggestions all depend on trustworthy historical data. Shipping UI on top of bad data would create misleading output faster.

### 2. The core product is the draft kit workflow
The launchable user journey is:
1. configure league/scoring
2. aggregate projections
3. output fantasy-point rankings
4. export/download a usable draft sheet
5. optionally use the extension during the draft

### 3. UI/product completeness is now a larger risk than backend planning
Backend/data/spec planning is relatively advanced. The bigger unknown is whether the actual user journey is defined and built well enough to ship.

### 4. Extension work is too risky to be the September critical path
The extension involves platform adapters, draft-room DOM variability, auth/session/payment integration, and real-time UX. Since it has not started, it should not block the web launch.

### 5. ML should prove value quickly or stop blocking progress
There is substantial ML planning, but no real backfill → train → validate cycle yet. ML should be treated as a launch enhancement unless it validates quickly.

---

## Launch Objective

### Must ship by draft season
- [ ] Trustworthy stat/projection data for launch-critical workflows
- [ ] Web draft kit workflow
- [ ] Fantasy-point rankings output
- [ ] Spreadsheet/downloadable draft sheet
- [ ] Usable desktop-first UI

### Nice to ship by draft season
- [ ] ML trends overlay, if validated
- [ ] Extension MVP, if capacity allows

### Explicit non-goal for critical path
- [ ] Do **not** make the extension a hard blocker for the September launch

---

## Current Status by Phase

### Phase 1 — Foundation & Data Pipeline
**Status:** mostly complete  
**What’s true now:** no longer the main strategic blocker, but unresolved scraper correctness still affects launch readiness.

### Phase 2 — Aggregation Dashboard / Draft Kit
**Status:** backend/spec work advanced, product workflow incomplete  
**What’s true now:** not done in launch terms; the actual draft kit user experience still needs definition and implementation.

### Phase 3a — Scrapers & Expanded Data Sources
**Status:** implemented enough to proceed, still being hardened  
**What’s true now:** feature-complete-ish, but not yet fully trusted operationally.

### Phase 3b — Smoke Test / Verification
**Status:** framework exists, launch-confidence still being earned  
**What’s true now:** “complete” procedurally, but still dependent on current data-quality work.

### Phase 3c — Feature Engineering
**Status:** significantly specified / partially implemented  
**What’s true now:** ahead of UI/extension, but still not proven by a real full ML run.

### Phase 3d / 3e / 3f — Model Training / Inference / Retraining
**Status:** planned more than proven  
**What’s true now:** not launch-grade until a real backfill → train → validate cycle succeeds.

### Phase 4 — Extension
**Status:** not started  
**What’s true now:** most risky major workstream; should not be the September critical path.

---

## Milestone Plan

## Milestone A — Finish data foundation
**Window:** 2026-03-28 → 2026-04-19

**Why this comes first:** all rankings, exports, ML, and extension suggestions depend on it.

- [ ] Finish Hockey Reference multi-team/career dedup
- [ ] Finish remaining NHL.com aggregate/realtime correctness work
- [ ] Finish NST `toi_sh` correctness work
- [ ] Add/run backfill verification workflow
- [ ] Verify launch-critical fields for rankings/output/export
- [ ] Document trusted data baseline

**Done means:**
- [ ] No known critical scraper correctness bugs remain
- [ ] Historical backfill is verified for launch-critical stats
- [ ] Data-quality verification steps are repeatable and documented

**Launch gate A:** Do not move to product build work unless the data baseline is trusted.

## Milestone B — Lock the draft kit workflow
**Window:** 2026-04-20 → 2026-05-03

**Why this comes second:** current product ambiguity is a bigger risk than code volume.

- [ ] Define exact launch user flow from setup → rankings → export
- [ ] Define supported scoring/league workflows at launch
- [ ] Define required screens/routes/components
- [ ] Define must-have vs post-launch features
- [ ] Decide whether extension is required for September launch (recommended: no)

**Done means:**
- [ ] One agreed v1 workflow exists
- [ ] One agreed must-have feature list exists
- [ ] One agreed cut list exists

**Launch gate B:** No major UI/product ambiguity remains.

## Milestone C — Complete draft kit backend path
**Window:** 2026-05-04 → 2026-06-01

**Why this comes before frontend implementation:** UI should build on stable contracts and stable output shape.

- [ ] Finalize scoring config backend path
- [ ] Finalize aggregation compute path
- [ ] Finalize fantasy-point output path
- [ ] Ensure export uses the same canonical output pipeline
- [ ] Ensure APIs are stable for frontend integration

**Done means:**
- [ ] A user can produce rankings/fantasy-point output from valid inputs
- [ ] Export data path is coherent with rankings path
- [ ] No blocker-level backend gaps remain for UI implementation

**Launch gate C:** Backend supports the real product workflow end-to-end.

## Milestone D — Build the web draft kit UI
**Window:** 2026-06-02 → 2026-07-06

**Why this is the main build phase:** this is the actual product most users will touch.

- [ ] Build league/scoring setup UI
- [ ] Build source weighting / kit configuration UI
- [ ] Build rankings/results UI
- [ ] Build export/download UI
- [ ] Build minimal saved kit/auth path if in launch scope
- [ ] Dogfood the full user workflow internally

**Done means:**
- [ ] A real user can go from setup → rankings → export
- [ ] Core desktop UX is usable without manual workarounds
- [ ] Product is internally dogfoodable

**Launch gate D:** The web draft kit exists as a coherent workflow.

## Milestone E — Make exports launch-grade
**Window:** 2026-07-07 → 2026-07-20

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

## Milestone F — Run the first real ML cycle
**Window:** 2026-07-21 → 2026-08-03

**Why here:** ML should prove itself after the data foundation and core draft kit path are stable.

- [ ] Run full backfill → train → validate cycle
- [ ] Evaluate output quality and usefulness
- [ ] Decide whether ML is:
  - [ ] launch-prominent
  - [ ] lightly surfaced
  - [ ] deferred

**Done means:**
- [ ] First real ML run completed
- [ ] Explicit go/no-go decision documented
- [ ] ML no longer sits in a speculative state

**Launch gate F:** ML is either validated for launch or explicitly made non-blocking.

## Milestone G — Harden the web launch
**Window:** 2026-08-04 → 2026-08-24

**Why this matters:** late August is the last safe stabilization window before draft season pressure.

- [ ] Fix critical workflow bugs
- [ ] Polish top-priority UI/UX issues
- [ ] Verify export and rankings stability
- [ ] Verify auth/payment basics if applicable
- [ ] Run end-to-end checks on the core journey

**Done means:**
- [ ] No critical defects in the core web workflow
- [ ] Rankings, exports, and draft prep flows are stable
- [ ] Product is safe to put in front of real users

**Launch gate G:** Web draft kit is launch-ready.

## Milestone H — Extension go/no-go
**Window:** 2026-08-25 → 2026-08-31

**Why this checkpoint exists:** to prevent the extension from derailing a ready web product.

- [ ] Assess whether the web product is stable
- [ ] Assess remaining engineering capacity
- [ ] Decide whether extension MVP is feasible for September

**Done means:**
- [ ] Explicit decision: proceed or defer
- [ ] If proceeding, MVP scope is tightly constrained

**Launch gate H:** Extension only proceeds if the web launch is already safe.

## Milestone I — Extension MVP / beta (conditional)
**Window:** 2026-09-01 → 2026-09-14

**Why this is conditional:** highest-risk, least-started workstream.

- [ ] Implement one platform first if necessary
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
- [ ] usable web UI
- [ ] spreadsheet/export product

### Tier 2 — important, but should not block launch
- [ ] first real ML run
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

### If behind by late June
- [ ] treat export as primary draft-day product
- [ ] simplify rankings UI before adding breadth

### If behind by late July
- [ ] make ML optional or defer launch visibility
- [ ] do not let ML block the draft kit

### If behind by late August
- [ ] defer extension
- [ ] launch web draft kit only

---

## Final Launch Recommendation

The highest-probability draft-season success path is:

- ship the web draft kit first
- make exports strong enough to be useful during drafts
- let ML ship only if validated
- let the extension ship only if it does not endanger the web launch

This gives PuckLogic the best chance of having a genuinely usable product by mid-September instead of a partially finished all-at-once launch.
