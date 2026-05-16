# Workflow State

**Active Phase:** review — Milestone F (VORP export column)  
**Active Branch:** feature/012-export-polish (PR #38)  
**Active Artifacts:** `docs/research/006-vorp-export-column-brainstorm.md`, `docs/specs/013-vorp-export-column.md`, `docs/plans/013-vorp-export-column.md`, `docs/specs/013-vorp-export-column-adversarial-pr-review-r1.md`  
**Current Gate:** pre-ship — adversarial PR/QA review APPROVED WITH NITS (I-1, M-1, M-2)  
**Blockers:** none  
**Next Action:** resolve nits (I-1: add PDF cell em-dash test; M-1: move _NOTES to module scope) or accept and ship-sync  
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

**Milestone C:** complete — PR #36 merged 2026-05-06
**Milestone D:** complete — PR #37 merged 2026-05-10
**Milestone E:** PR #38 open; adversarial review round 2 APPROVED WITH NITS — see `docs/specs/012-export-polish-adversarial-pr-review-r2.md`; all three prior blockers resolved; M-1/M-2/M-3 nits fixed and verified (25 backend router tests, 203 frontend tests pass); I-1 deferred post-merge; ready for ship-sync
