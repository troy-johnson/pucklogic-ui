# Adversarial Review Packet — Plan 010a

**Artifact type:** plan
**Artifact path:** `docs/plans/010a-web-draft-kit-ui.md`
**Originating spec:** `docs/specs/010-web-ui-wireframes-design.md`
**Originating spec review status:** APPROVED WITH NITS
**Round number:** 1
**Intended outcome:** Implement Milestone D web draft kit UI in 5 waves without rework
**Reviewer lens:** correctness, architecture, security
**Required verdict set:** APPROVED | APPROVED WITH NITS | BLOCKED | NEEDS CLARIFICATION

---

## Key claims under review

1. Login/signup at `(auth)/login` and `(auth)/signup` are correctly placed within the auth route group
2. Middleware correctly matches and protects auth-required routes using `(auth)/**` path syntax
3. Draft session API client endpoints (`/draft-sessions`, `/reconnect`, `/picks`) match the backend contract
4. `/draft-sessions/active` endpoint exists for live session hydration in Task 5.5
5. `dashboard/page.tsx` → Server Component refactor in Task 3.8 is a simple wrapper swap

---

## Changed files in scope

- `docs/plans/010a-web-draft-kit-ui.md` — full implementation plan under review

---

## Verification commands run

```bash
# Check actual dashboard page type
head -5 apps/web/src/app/dashboard/page.tsx

# Check actual backend draft-session endpoints
grep -n "@router\|def " apps/api/routers/draft_sessions.py
```

---

## Findings

### F-1 — BLOCKER: Login/signup inside `(auth)` route group causes infinite redirect loop

**Evidence:** Plan file surface lists `apps/web/src/app/(auth)/login/page.tsx` and `apps/web/src/app/(auth)/signup/page.tsx`. The `(auth)/layout.tsx` (Task 2.6) redirects unauthenticated users to `/login`. Since `/login` resolves from `(auth)/login/page.tsx`, accessing `/login` while unauthenticated applies `(auth)/layout.tsx`, which redirects to `/login` again — infinite loop.

**Recommendation:** Move login and signup outside the `(auth)` route group:
- `src/app/login/page.tsx`
- `src/app/signup/page.tsx`

Update middleware matcher to explicitly exclude `/login` and `/signup` from the redirect rule. Update Task 3.9 file paths accordingly.

---

### F-2 — BLOCKER: Middleware path matching describes `(auth)/**` syntax that does not match any real URL

**Evidence:** Task 2.5 states the redirect rule as "if path matches `/(auth)/**` and no session → redirect to `/login`". AC-7 describes "unauthenticated request to `(auth)/**`". Next.js route groups (`(auth)`) are a file-system-only convention — they never appear in the URL. The actual URL for `(auth)/dashboard/page.tsx` is `/dashboard`. Code that checks `pathname.startsWith('/(auth)/')` will never match any real request and silently fails to protect any route.

**Recommendation:** Rewrite Task 2.5 redirect logic to match actual URL paths. Recommended pattern:

```ts
const PUBLIC_PATHS = ['/', '/login', '/signup', '/auth/callback']
const isPublic = PUBLIC_PATHS.some(p => pathname === p) || pathname.startsWith('/_next')
if (!isPublic && !session) return NextResponse.redirect(new URL('/login', request.url))
if (pathname === '/' && session) return NextResponse.redirect(new URL('/dashboard', request.url))
```

Update AC-7 to: "Unauthenticated request to `/dashboard` redirects to `/login`".

---

### F-3 — BLOCKER: Draft session API endpoints do not match the backend contract

**Evidence:** `apps/api/routers/draft_sessions.py` defines:
- `POST /draft-sessions/start` (not `POST /draft-sessions`)
- `POST /draft-sessions/{session_id}/resume` (not `/reconnect`)
- `POST /draft-sessions/{session_id}/manual-picks` (not `/picks`)
- `POST /draft-sessions/{session_id}/end` ✓
- `GET /draft-sessions/{session_id}/sync-state` (not in plan at all)
- No `/draft-sessions/active` endpoint exists anywhere

Plan Task 4.2 exports functions that POST to wrong paths. All session API calls would 404 at runtime.

**Recommendation:** Update Task 4.2 with correct endpoint map:
```
createSession  → POST /draft-sessions/start
resumeSession  → POST /draft-sessions/{id}/resume
recordPick     → POST /draft-sessions/{id}/manual-picks
endSession     → POST /draft-sessions/{id}/end
fetchSyncState → GET  /draft-sessions/{id}/sync-state   (add this — needed by LiveDraftScreen)
```

Update Task 4.1 test descriptions to match.

---

### F-4 — IMPORTANT: `dashboard/page.tsx` is a `'use client'` component — Task 3.8 understates the refactor cost

**Evidence:** `apps/web/src/app/dashboard/page.tsx` line 1: `"use client"`. It uses `useState`, `useEffect`, `useStore`, and calls API functions directly with token from session state. Task 3.8 describes this as "refactor to use PreDraftWorkspace; Server Component data fetch" — a framing that implies minimal change.

Actual work required: remove `'use client'`, remove all `useState`/`useEffect`/`useStore` hooks, rewrite data fetching as `async` server-side with `supabase.auth.getSession()` token, pass fetched data as props. This is a near-rewrite of the page, not a wrapper swap. The verification command (`pnpm build`) won't catch runtime errors from leftover client hooks.

**Recommendation:** Add explicit steps to Task 3.8:
1. Delete `'use client'` directive
2. Remove all `useState`, `useEffect`, `useStore` imports and call sites
3. Convert page to `async function` with server-side data fetch
4. Add test covering that the page renders without a `useStore` import: `grep -L "useStore" src/app/(auth)/dashboard/page.tsx`

---

### F-5 — IMPORTANT: No `/draft-sessions/active` endpoint — Task 5.5 live session hydration has no implementation path

**Evidence:** `GET /draft-sessions/active` does not exist in `apps/api/routers/draft_sessions.py`. Task 5.5 says the live page "fetches active session from `/draft-sessions/active` (or reads sessionId from cookie)". The "or reads sessionId from cookie" fallback is the correct approach but is not specified.

**Recommendation:** Drop the `/draft-sessions/active` reference entirely. Task 5.5 live page should: (1) read `sessionId` from `draftSession` Zustand store; (2) if `sessionId === null`, redirect to `/dashboard`; (3) if `sessionId` exists, call `fetchSyncState(sessionId, token)` via the existing `GET /{id}/sync-state` endpoint to hydrate initial state. The `sessionId` is written to the store by the "Start live draft" flow that precedes navigation to `/live`.

---

### F-6 — MINOR: AC-7 references `(auth)/**` path syntax (same root cause as F-2)

AC-7: "Unauthenticated request to `(auth)/**` redirects to `/login`" — this is not a testable URL pattern. Should read: "Unauthenticated request to `/dashboard` redirects to `/login`".

---

### F-7 — MINOR: Middleware Vitest testing requires Edge Runtime mock setup not mentioned in the plan

Next.js middleware runs in Edge Runtime; Vitest runs in Node. Testing `middleware.ts` with Vitest requires mocking `NextRequest`, `NextResponse`, and `@supabase/ssr`. This is achievable but is non-trivial — the plan implies it's a single-command task. In practice, the mock setup may take 30–60 min. Not a blocker but the implementor should be aware.

---

## Verdict

**APPROVED WITH NITS**

Round 1 verdict was BLOCKED on F-1, F-2, F-3. All 5 corrections applied 2026-05-07. Residual gap (`draft-session-id` cookie write ownership) closed 2026-05-07 by adding Task 4.5 (`StartDraftModal.tsx`) with AC-23. All findings are resolved.

## Corrections applied (2026-05-07)

| Finding | Correction |
|---|---|
| F-1 | Login/signup moved to `src/app/login/` and `src/app/signup/` outside `(auth)` group; Task 3.9 and file surface updated |
| F-2 | Task 2.5 rewritten with actual URL path matching (`PUBLIC_PATHS` exclusion list); AC-7 and AC-21 updated to reference real URL paths |
| F-3 | Task 4.1 test descriptions and Task 4.2 endpoint map corrected to match backend: `/start`, `/resume`, `/manual-picks`; `fetchSyncState` (GET `/{id}/sync-state`) added |
| F-4 | Task 3.8 expanded with explicit 6-step hook-removal sequence and grep verification command |
| F-5 | Task 5.5 `page.tsx` rewritten: reads `sessionId` from `draft-session-id` cookie; calls `fetchSyncState`; no reference to non-existent `/draft-sessions/active` |
| Residual (cookie write) | Task 4.5 added: `StartDraftModal.tsx` owns the `createSession` call, `draft-session-id` cookie write, `startSession` Zustand dispatch, and `router.push('/live')`; AC-23 covers cookie write assertion |

## Remaining open items

- **F-7 (minor, accepted):** Middleware Vitest/Edge Runtime mock setup is non-trivial; implementor should budget 30–60 min for Task 2.4/2.5 mock scaffolding. Not a plan failure.

---

## Downstream requirements

- Adversarial PR/QA review: **required** for `middleware.ts`, `(auth)/layout.tsx`, `auth/callback/route.ts`, `StartDraftModal.tsx`
- Ship gate note: all AC items must be green and PR/QA adversarial review must pass before merge

---

# PR/QA Adversarial Review — PR #37

**Branch:** `feat/milestone-d-web-ui`
**PR:** [#37](https://github.com/troy-johnson/pucklogic-ui/pull/37)
**Reviewed against:** plan 010a (Approved with nits, r1 corrections applied)

## Round 1 (self-review, 2026-05-09)

**Reviewer lens:** correctness, plan alignment
**Verdict:** REVISE

### Findings

| ID | Severity | File | Finding |
|---|---|---|---|
| B-1 | Blocker | `app/(auth)/live/page.tsx:27-29` | Both branches of `players` ternary return `[]`; `void sources` discards fetched data. `/live` always renders empty regardless of session state. |
| B-2 | Blocker | dashboard layout | `StartDraftModal` exists and is tested but has no call site — user has no UI path to start a draft session. |
| I-1 | Important | `StartDraftModal.tsx:32` | `draft-session-id` cookie missing `Secure` flag, no `Max-Age` (session cookie), `endSession` doesn't clear it. |
| I-2 | Important | `KitSwitcher.tsx:131-141` | Overflow menu uses `window.prompt()` placeholder shipping in production. |
| I-3 | Important | `LiveDraftScreen` hydration | No mechanism to hydrate Zustand store from server-fetched `syncState`; hard refresh during `/live` loses picks/mode. |
| M-1 | Medium | `draftSession.ts:46` | `endSession()` only resets `status`/`mode`, leaves `sessionId`/`kitId`/`picks` populated. |

### Resolutions (commit `c96f56d`, `235c09b`)

- B-1 → `live/page.tsx` passes real `syncState`; new `hydrateSession` slice action populates store on mount
- B-2 → New `StartDraftButton` client island wired into dashboard kit-context bar
- I-1 → New `lib/draft-session-cookie.ts` with `Secure`/`Max-Age=24h`/`clearDraftSessionCookie`
- I-2 → Real `role="menu"` dropdown with click-outside detection; `window.prompt` removed
- I-3 → `SyncStateResponse.kit_id` optional; `hydrateSession` accepts `kitId` with fallback
- M-1 → `endSession()` now fully resets state via `INITIAL_STATE` spread

## Round 2 (external review, 2026-05-09)

**Reviewer:** external review disposition (inline; not written to disk)
**Verdict:** REVISE — ship gate BLOCKED

### Findings

| ID | Severity | File | Finding |
|---|---|---|---|
| B2-1 | Blocker | `app/(auth)/live/page.tsx` | `players={[]}` and `myTeamPlayers={[]}` — core draft experience renders blank board on hard navigation/refresh |
| B2-2 | Blocker | `app/(auth)/dashboard/page.tsx` | Pre-draft workspace passes empty data — workspace reachable but functionally blank |
| B2-3 | Blocker | dashboard layout | `KitSwitcher` not reachable from app UI; only static context buttons present |
| I2-1 | Important | `lib/api/__tests__/user-kits.test.ts` | Token-auth API surface (`listKits`/`createKit`/etc.) lacks direct test coverage |
| I2-2 | Important | `app/(auth)/layout.tsx` | Silent fallback to 0 draft passes on entitlement fetch failure can mask auth/API outages |
| I2-3 | Important | (informational) | High-risk auth/session paths touched: middleware, auth layout, PKCE callback, JS-writable draft-session cookie, live session hydration |
| m2-1 | Minor | `lib/draft-session-cookie.ts` | `clearDraftSessionCookie()` defined but unused; stale cookies persist after session end |
| m2-2 | Minor | (structural) | `draft-session-id` is JS-writable by design; XSS could tamper. Mitigated by `SameSite=Lax` + conditional `Secure` + 24h `Max-Age` |

### Resolutions (commit `c44bf4f`)

- B2-1 + B2-2 → New `lib/rankings/load-initial.ts` server-side helper. Fetches sources, default scoring preset, computes baseline rankings with equal weights. Both `/dashboard` and `/live` consume it; `LiveDraftScreen` and `PreDraftWorkspace` render real ranked players.
- B2-3 → New `KitContextSwitcher` client island. Loads kits via `listKits(token)` on mount, populates Zustand store, replaces static "Draft Kit" button. Click opens existing `KitSwitcher` drawer.
- I2-1 → 5 new tests in `user-kits.test.ts` covering path, method, and `Authorization: Bearer` header for each token-auth function.
- I2-2 → `(auth)/layout.tsx` now `console.error`s entitlement failures; degraded "0 passes" state distinguishable from real zero-balance accounts in server logs.
- m2-1 → `clearDraftSessionCookie()` wired into new "End draft" button in `LiveDraftScreen` (calls `endSession()` + clears cookie + routes to `/dashboard`).
- m2-2 → Accepted as structural. The cookie must be JS-writable for the start-draft flow (Task 4.5). Mitigations remain: `SameSite=Lax`, conditional `Secure`, `Max-Age=24h`, server-side validation via `fetchSyncState`. Documented as accepted risk.
- I2-3 → Acknowledged. Auth-surface changes covered by middleware unit tests, auth-pages tests, and StartDraftModal cookie-write assertion. Remains gated on adversarial PR/QA review (this packet) before merge.

### Round 2 status

All blockers and important findings resolved. Awaiting reviewer confirmation that the resolutions clear the ship gate.

## Round 3 (initial-review minors, 2026-05-10)

Self-review minors flagged in PR/QA round 1 but deferred at the time, addressed pre-emptively in commit `ba8bfa9` to clean up the diff before final reviewer pass.

| ID | Severity | File | Finding |
|---|---|---|---|
| m-1 | Minor | `lib/rankings/load-initial.ts` | `fetchSources` / `fetchScoringConfigPresets` / `computeRankings` called without a token; inconsistent with `(auth)/layout.tsx` which passes it. Brittle if endpoints later require auth. |
| m-2 | Minor | `auth/callback/route.ts`, `app/login/page.tsx`, `middleware.ts` | `next` query param ignored — users always land on `/dashboard` after login regardless of intended destination. |
| m-3 | Minor | `auth/callback/route.ts` | Silently swallows `exchangeCodeForSession` errors with only `?error=auth_callback_failed` in URL; no server-side log. |
| m-4 | Minor | `KitSwitcher.tsx` | `updateKit` imported from API and also destructured from store (renamed to `updateKitStore`); read-confusing. |

### Resolutions (commit `ba8bfa9`)

- m-1 → All three API functions now accept optional `token`; `loadInitialRankings` forwards it; `dashboard/page.tsx` fetches `session.access_token` before calling; `live/page.tsx` reuses the token it already had. Public endpoints continue to work since the token is optional.
- m-2 → Middleware preserves intended path as `?next=<path>` (skipping when target is `/dashboard`); new `lib/safe-next.ts` `safeNextPath()` validates that the value starts with `/` and isn't protocol-relative; login page reads via `useSearchParams` and uses the validated path on `router.push`; auth callback honors the same param. Login page wraps the form in `<Suspense>` for static prerender compatibility.
- m-3 → `auth/callback/route.ts` now `console.error`s both exchange failures and missing-code requests, mirroring the entitlements logging in `(auth)/layout.tsx`.
- m-4 → KitSwitcher API imports aliased (`apiCreateKit` / `apiDeleteKit` / `apiDuplicateKit` / `apiUpdateKit`); store action keeps the natural `updateKit` name.

### Round 3 status

All initial-review minors resolved.

## Round 4 (Codex automated review, 2026-05-10)

GitHub PR comments from `chatgpt-codex-connector[bot]` flagging two findings on the open PR.

| ID | Severity | File | Comment ID | Finding |
|---|---|---|---|---|
| C-1 | P1 | `app/(auth)/live/page.tsx` | 3214125230 | `players` hardcoded to `[]` in both ternary branches; `/live` renders empty even when `fetchSyncState` succeeds. (Reviewed against early commit `a004bc36c5` — superseded.) |
| C-2 | P2 | `components/ManualPickDrawer.tsx:31` | 3214125232 | `round` / `pick` initialized from props once via `useState`; drawer stays mounted across open/close, so subsequent openings keep stale values. After the draft advances, manual picks could be recorded against the wrong round/pick numbers. |

### Resolutions

- C-1 → Already resolved before the comment was posted, in commit `c44bf4f`. Current `live/page.tsx` passes `rankings` from `loadInitialRankings(token)` to `LiveDraftScreen.players`. No additional change needed.
- C-2 → Real bug, fixed. Added a `useEffect` that re-syncs `round`/`pick` state to the live `currentRound`/`currentPick` props each time `open` flips to `true`. Regression test added that mounts the drawer with `{round: 1, pick: 1}`, closes/reopens with `{round: 3, pick: 5}`, and asserts the inputs reflect the new defaults.

### Round 4 status

All Codex findings resolved. **182 tests passing, build clean.** No outstanding findings from any review round.

---

## Test/build evidence

- `pnpm --filter @pucklogic/web test` → 182/182 passing across 26 files
- `pnpm --filter @pucklogic/web build` → exits 0; routes `/`, `/auth/callback`, `/dashboard`, `/live`, `/login`, `/signup` all compile
- New tests added in remediation across all rounds: 17
  - Round 1: 4 (hydrateSession kitId×2, KitSwitcher dropdown×2)
  - Round 2: 9 (5 user-kits token-auth + 3 KitContextSwitcher + 1 LiveDraftScreen mock fix)
  - Round 3: 7 (5 safeNextPath unit + 2 middleware next-redirect preservation)
  - Round 4: 1 (ManualPickDrawer reopen-prop-sync regression test)
