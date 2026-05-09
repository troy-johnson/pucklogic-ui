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

- Adversarial PR/QA review: **required** for `middleware.ts`, `(auth)/layout.tsx`, `auth/callback/route.ts`
- Ship gate note: all AC items must be green and PR/QA adversarial review must pass before merge
