# Workflow State

**Active Phase:** idle  
**Active Branch:** main  
**Active Artifacts:** none  
**Current Gate:** none  
**Blockers:** none  
**Next Action:** begin next milestone — no active track  
**Active Snapshot Pointer:** none

> This file is a current pointer, not a full session log.

---

## Context

**Track:** research → brainstorm → spec → plan → implement-tdd → review → ship-sync (complete)
**Milestone D status:** COMPLETE — PR #37 merged to main 2026-05-10
**Plan 010a status:** Implemented — all 27 tasks, 23 AC items shipped and merged
**Spec 010 status:** Approved with nits — 2026-05-06

**What landed in PR #37:**
- Design system token layer + shadcn bridge + Inter/JetBrains Mono fonts
- AppShell, UserProvider, middleware (PUBLIC_PATHS exclusion), (auth)/layout auth gate
- Value prop landing page, dashboard moved into (auth) route group
- KitSwitcher, KitContextSwitcher, PreDraftWorkspace, kits Zustand slice
- Login/signup pages + auth/callback PKCE route
- Draft-sessions API client, draftSession Zustand slice, StartDraftModal
- LiveDraftScreen, ManualPickDrawer, ReconnectBanner, /live Server Component
- loadInitialRankings server-side helper, safeNextPath open-redirect guard
- draft-session-cookie utilities (Secure flag, Max-Age, clearDraftSessionCookie)
- 182 tests across 26 files

**Milestone C:** COMPLETE — PR #36 merged 2026-05-06
**Milestone D:** COMPLETE — PR #37 merged 2026-05-10
**Milestone E:** COMPLETE — PR #38 merged to main 2026-05-16 (squash commit 18154ce)
**Milestone F:** COMPLETE — shipped in PR #38; spec 013, plan 013, brainstorm 006

**What landed in PR #38:**
- POST /exports/generate wired to PreDraftWorkspace XLSX + PDF download buttons
- Deterministic export filenames (season/date/context slug)
- Kit-pass gating enforced on export endpoint
- Missing-context and error states in the UI
- "Projected Fantasy Value" → "Value Over Replacement" in all XLSX sheets and PDF header
- Null VORP → "—" (em-dash) in both XLSX sheets; 0.0 treated as valid replacement-level value
- PDF conditional asterisk + footnote for null-VORP rows (league profile conversion nudge)
- XLSX Notes tab (third sheet) with three canonical glossary entries
- First-load export weights fallback via initialWeights prop (prevents empty source_weights 422)
- 71 backend + 204 frontend tests
