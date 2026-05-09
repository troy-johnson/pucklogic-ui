# Plan 010a — Milestone D: Web Draft Kit UI

**Spec basis:** `docs/specs/010-web-ui-wireframes-design.md`
**Status:** Approved with nits — adversarial review r1 corrections applied 2026-05-07
**Date:** 2026-05-06
**Risk Tier:** 2 — Cross-route UI, auth, state management, app shell
**Scope:** Large (~4–5 days, multi-wave, 27 tasks, 23 AC items)
**Execution mode:** Dependency waves (confirm: subagent dispatch / inline / batch)

---

## Goal

Build the Milestone D web draft kit UI: design system token layer, app shell, value prop landing page, auth flow, pre-draft workspace with kit management, session state, and live draft screen.

## Non-Goals

- Browser extension DOM parsing (Milestone I)
- In-season trends tab / v2.0 UI (deferred per apps/web/CLAUDE.md)
- Multi-user collaboration
- `/rankings` public default-rankings browsing page (post-launch)
- Mobile-responsive polish beyond desktop-first layout

---

## Acceptance Criteria

### Wave 1 — Design system baseline

- [ ] AC-1: All CSS custom properties from spec 010 color table present in `globals.css` — `grep -c "accent-blue\|bg-base\|bg-surface\|text-primary\|--primary:" apps/web/src/app/globals.css` ≥ 15
- [ ] AC-2: `--primary` shadcn token mapped to HSL equivalent of `#34d399` in `globals.css`
- [ ] AC-3: Inter and JetBrains Mono loaded via `next/font`, className applied to `<html>` in root `layout.tsx`
- [ ] AC-4: `pnpm --filter @pucklogic/web build` exits 0

### Wave 2 — Shell + landing

- [ ] AC-5: `AppShell.test.tsx` passes — renders "PuckLogic" logo, `passBalance` prop as "N passes", user-menu button
- [ ] AC-6: `src/app/page.tsx` test passes — no "Coming soon" text; nav, hero, and steps strip present
- [ ] AC-7: Unauthenticated request to `/dashboard` redirects to `/login` — verified by middleware unit test
- [ ] AC-8: Authenticated request to `/` redirects to `/dashboard` — verified by middleware unit test
- [ ] AC-9: `pnpm --filter @pucklogic/web test` all green after wave 2

### Wave 3 — Pre-draft workspace

- [ ] AC-10: `KitSwitcher.test.tsx` passes — kit list renders, active kit has checkmark, new-kit button and overflow menu present
- [ ] AC-11: `PreDraftWorkspace.test.tsx` passes — RankingsTable and right panel with weight sliders and export buttons render
- [ ] AC-12: `kits.slice.test.ts` passes — setActiveKit, setKits, createKit, deleteKit, updateKit actions
- [ ] AC-13: Login page renders email + password form; signup page renders email + password + confirm form — verified by test
- [ ] AC-14: `pnpm --filter @pucklogic/web test` all green after wave 3

### Wave 4 — Session API + state

- [ ] AC-15: `draft-sessions.test.ts` passes — createSession, resumeSession, recordPick, endSession (mock apiFetch)
- [ ] AC-16: `draftSession.slice.test.ts` passes — startSession, recordPick, setMode (sync/manual/reconnecting/disconnected), endSession, reset
- [ ] AC-17: `store/index.ts` composes kits + draftSession slices; `pnpm --filter @pucklogic/web build` TypeScript clean
- [ ] AC-23: `StartDraftModal.test.tsx` passes — confirmation renders, createSession called on confirm, router.push('/live') called on success; `draft-session-id` cookie write verified via `document.cookie` assertion

### Wave 5 — Live draft screen

- [ ] AC-18: `LiveDraftScreen.test.tsx` passes — available players list, suggestion cards (priority/alt/sleeper), roster needs grid, team list, sync status indicator
- [ ] AC-19: `ManualPickDrawer.test.tsx` passes — player search, row selection, confirm button, success flash
- [ ] AC-20: `ReconnectBanner.test.tsx` passes — visible in reconnecting/disconnected states, hidden when mode is sync
- [ ] AC-21: `/live` route only accessible to authenticated users — middleware public-paths exclusion list does not include `/live`; verified by middleware unit test
- [ ] AC-22: `pnpm --filter @pucklogic/web test && pnpm --filter @pucklogic/web build` both exit 0

---

## File Surface

### Created

| File | Wave | Purpose |
|---|---|---|
| `apps/web/src/middleware.ts` | 2 | Session refresh (updateSession), route protection, `/` → `/dashboard` redirect for auth users |
| `apps/web/src/app/(auth)/layout.tsx` | 2 | Auth gate: getUser → redirect `/login` if unauthenticated; fetch entitlements; render UserProvider + AppShell |
| `apps/web/src/app/(auth)/dashboard/layout.tsx` | 2 | Kit context bar layout wrapper |
| `apps/web/src/app/login/page.tsx` | 3 | Login form — outside (auth) group to avoid redirect loop; Supabase signInWithPassword; on success router.push('/dashboard') |
| `apps/web/src/app/signup/page.tsx` | 3 | Signup form — outside (auth) group; Supabase signUp; on success show email confirmation message |
| `apps/web/src/app/auth/callback/route.ts` | 3 | Supabase PKCE code exchange; redirects to /dashboard on success (F-1: full navigation satisfies router.refresh requirement) |
| `apps/web/src/app/(auth)/live/layout.tsx` | 5 | Live-mode layout: no kit context bar; renders ReconnectBanner above children |
| `apps/web/src/app/(auth)/live/page.tsx` | 5 | Live draft route; renders LiveDraftScreen |
| `apps/web/src/components/UserProvider.tsx` | 2 | `'use client'`; initialUser prop; onAuthStateChange subscription; exports useUser() |
| `apps/web/src/components/AppShell.tsx` | 2 | Shell header: logo, passBalance prop, UserMenuButton (client) |
| `apps/web/src/components/KitSwitcher.tsx` | 3 | Right slide-in panel: kit list, active indicator, new-kit form, overflow menu (rename/duplicate/delete) |
| `apps/web/src/components/PreDraftWorkspace.tsx` | 3 | Rankings table + right panel (SourceWeightSelector, league profile placeholder, export buttons) |
| `apps/web/src/components/LiveDraftScreen.tsx` | 5 | Full live draft layout: available players + suggestion/needs/team right panel |
| `apps/web/src/components/ManualPickDrawer.tsx` | 5 | Slide-in: player search, row select, confirm pick, "Recorded" flash |
| `apps/web/src/components/ReconnectBanner.tsx` | 5 | Inline banner: reconnecting/disconnected states, switch-to-manual action |
| `apps/web/src/store/slices/kits.ts` | 3 | Active kit selection; kit CRUD in Zustand |
| `apps/web/src/lib/api/entitlements.ts` | 3 | GET /entitlements client |
| `apps/web/src/lib/api/draft-sessions.ts` | 4 | POST /draft-sessions/start, /{id}/resume, /{id}/manual-picks, /{id}/end; GET /{id}/sync-state |
| `apps/web/src/store/slices/draftSession.ts` | 4 | Live session state: picks, mode, status |
| `apps/web/src/components/StartDraftModal.tsx` | 4 | 'use client'; createSession → write draft-session-id cookie → startSession dispatch → router.push('/live') |
| `apps/web/src/components/__tests__/AppShell.test.tsx` | 2 | — |
| `apps/web/src/components/__tests__/KitSwitcher.test.tsx` | 3 | — |
| `apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx` | 3 | — |
| `apps/web/src/components/__tests__/LiveDraftScreen.test.tsx` | 5 | — |
| `apps/web/src/components/__tests__/ManualPickDrawer.test.tsx` | 5 | — |
| `apps/web/src/components/__tests__/ReconnectBanner.test.tsx` | 5 | — |
| `apps/web/src/store/__tests__/kits.slice.test.ts` | 3 | — |
| `apps/web/src/store/__tests__/draftSession.slice.test.ts` | 4 | — |
| `apps/web/src/lib/api/__tests__/entitlements.test.ts` | 3 | — |
| `apps/web/src/lib/api/__tests__/draft-sessions.test.ts` | 4 | — |
| `apps/web/src/app/__tests__/page.test.tsx` | 2 | Landing page render test |
| `apps/web/src/app/__tests__/auth-pages.test.tsx` | 3 | Login + signup form render tests |
| `apps/web/src/__tests__/middleware.test.ts` | 2 | Redirect rule unit tests |

### Modified

| File | Wave | Change |
|---|---|---|
| `apps/web/src/app/globals.css` | 1 | Full PL token layer + shadcn bridge + `.pl-*` utility classes |
| `apps/web/tailwind.config.ts` | 1 | Extend theme: colors, fontFamily, borderRadius referencing CSS vars |
| `apps/web/src/app/layout.tsx` | 1 | Inter + JetBrains Mono via next/font; html className; remove placeholder |
| `apps/web/src/app/page.tsx` | 2 | Replace "Coming soon" with value prop landing page (Claude Design variant C) |
| `apps/web/src/app/(auth)/dashboard/page.tsx` | 3 | Refactor to use PreDraftWorkspace; Server Component data fetch |
| `apps/web/src/store/index.ts` | 3+4 | Compose kits slice (wave 3), draftSession slice (wave 4) |
| `apps/web/src/lib/api/user-kits.ts` | 3 | Verify/complete: listKits, createKit, updateKit, deleteKit, duplicateKit |
| `apps/web/CLAUDE.md` | 1 | Update status table to match actual implemented state; remove stale Phase 2 TODO markers |

### Moved

| From | To | Wave |
|---|---|---|
| `apps/web/src/app/dashboard/` | `apps/web/src/app/(auth)/dashboard/` | 2 |

---

## Task List

### Wave 1 — Design system baseline
*No upstream dependencies. Start here.*

**Task 1.1 — Update `apps/web/CLAUDE.md` to reflect actual implemented state**
Edit status table: mark `SourceWeightSelector.tsx`, `RankingsTable.tsx`, `dashboard/page.tsx`, `store/slices/sources.ts`, `store/slices/rankings.ts`, `lib/api/index.ts`, `lib/supabase/` as ✅ Complete. Update slice paths from flat `store/*.ts` to `store/slices/*.ts`. Remove stale `⬜ TODO` markers for implemented items.
```bash
grep -c "TODO\|⬜" apps/web/CLAUDE.md
```
Expected: 0 stale TODO/⬜ markers after edit.

**Task 1.2 — Write full PL token layer and shadcn bridge in `globals.css`**
Write all CSS custom properties: dark theme (`:root` or `[data-theme="dark"]`), light theme (`[data-theme="light"]`), scrollbar styles (6px, `--border-mid` thumb), and `.pl-*` utility classes from spec 010 component primitives table. shadcn bridge: set `--primary`, `--primary-foreground`, `--background`, `--foreground`, `--card`, `--card-foreground`, `--border`, `--ring`, `--destructive`, `--muted`, `--accent` as HSL values derived from PL tokens.
```bash
grep -c "accent-blue\|bg-base\|bg-surface\|text-primary\|--primary:" apps/web/src/app/globals.css
```
Expected: count ≥ 15.

**Task 1.3 — Extend `tailwind.config.ts` with CSS var references**
In `theme.extend`: add `colors` mapping PL token names to `var(--*)` values; `fontFamily.sans` → `var(--font-sans)`; `fontFamily.mono` → `var(--font-mono)`; `borderRadius` entries for 4px, 6px, 8px, 99px.
```bash
pnpm --filter @pucklogic/web build 2>&1 | tail -5
```
Expected: exits 0 with no missing-token warnings.

**Task 1.4 — Wire Inter + JetBrains Mono in root `layout.tsx` via next/font**
Import `Inter` and `JetBrains_Mono` from `next/font/google`. Define `--font-sans` and `--font-mono` CSS variable names via the `variable` option. Apply both classNames to `<html>`. Remove any existing placeholder content from layout.
```bash
pnpm --filter @pucklogic/web build 2>&1 | tail -5
```
Expected: exits 0; no font-loading errors.

---

### Wave 2 — Shell + landing
*Depends on Wave 1.*

**Task 2.1 — Write failing tests for AppShell**
Create `src/components/__tests__/AppShell.test.tsx`. Tests: (a) renders text "PuckLogic"; (b) renders `passBalance={3}` as "3 passes"; (c) renders a button with accessible label "User menu".
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/AppShell.test.tsx 2>&1 | tail -10
```
Expected: fails — module `AppShell` not found.

**Task 2.2 — Create `src/components/UserProvider.tsx`**
`'use client'`. Accepts `initialUser: User | null`. Creates browser Supabase client via `createClient()`. Subscribes to `supabase.auth.onAuthStateChange` to keep `user` state current. Exports `UserContext` and `useUser(): User | null` hook.
```bash
pnpm --filter @pucklogic/web build 2>&1 | tail -5
```
Expected: TypeScript compiles; no type errors.

**Task 2.3 — Create `src/components/AppShell.tsx` and make tests pass**
Server Component outer shell. Props: `passBalance: number`, `children: ReactNode`. Renders `<header>` with: logo ("PuckLogic"), `<span>{passBalance} passes</span>`, `<UserMenuButton />` (a `'use client'` sub-component using `useUser()`). Wire AppShell into `(auth)/layout.tsx` in Task 2.5.
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/AppShell.test.tsx 2>&1 | tail -10
```
Expected: all AppShell tests pass.

**Task 2.4 — Write failing middleware redirect tests**
Create `src/__tests__/middleware.test.ts`. Mock `@supabase/ssr` `createServerClient`. Tests: (a) unauthenticated request to `/dashboard` → response redirects to `/login`; (b) authenticated request to `/` → response redirects to `/dashboard`; (c) unauthenticated request to `/` → no redirect (landing page served).
```bash
pnpm --filter @pucklogic/web test -- src/__tests__/middleware.test.ts 2>&1 | tail -10
```
Expected: fails — `middleware` module not found.

**Task 2.5 — Create `src/middleware.ts` and make middleware tests pass**
Use `@supabase/ssr` `createServerClient` with cookie read/write adapter. Call `supabase.auth.updateSession(request)` on every request. Route groups (`(auth)`) are file-system only and never appear in URLs — match actual URL paths:

```ts
const PUBLIC_PATHS = ['/', '/login', '/signup', '/auth/callback']
const isPublic = PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith('/_next'))
if (!isPublic && !session) return NextResponse.redirect(new URL('/login', request.url))
if (pathname === '/' && session) return NextResponse.redirect(new URL('/dashboard', request.url))
```

Matcher config: `'/((?!_next/static|_next/image|favicon.ico).*)' ` — runs on all routes; public-path exclusion happens in the handler body.
```bash
pnpm --filter @pucklogic/web test -- src/__tests__/middleware.test.ts 2>&1 | tail -10
```
Expected: all middleware redirect tests pass.

**Task 2.6 — Create `src/app/(auth)/layout.tsx`**
Server Component. Calls `createClient()` (server), `supabase.auth.getUser()`. If `!user` → `redirect('/login')`. Calls `apiFetch<EntitlementsResult>('/entitlements', { token: session.access_token })` to get `passBalance`. Renders: `<UserProvider initialUser={user}><AppShell passBalance={balance}>{children}</AppShell></UserProvider>`.
```bash
pnpm --filter @pucklogic/web build 2>&1 | tail -5
```
Expected: TypeScript compiles; no import or type errors.

**Task 2.7 — Move `src/app/dashboard/` to `src/app/(auth)/dashboard/` and create `(auth)/dashboard/layout.tsx`**
```bash
mv apps/web/src/app/dashboard apps/web/src/app/\(auth\)/dashboard
```
Create `(auth)/dashboard/layout.tsx`: renders kit context bar (kit name button → opens KitSwitcher, league profile dropdown, weights dropdown, "▶ Compute" button). Props: `activeKitName: string`.
```bash
pnpm --filter @pucklogic/web build 2>&1 | tail -5
```
Expected: exits 0; no broken imports from the move.

**Task 2.8 — Write failing landing page test and replace `src/app/page.tsx`**
Create `src/app/__tests__/page.test.tsx`. Tests: no "Coming soon" text; "PuckLogic" logo present in nav; "01" step text present; at least one CTA button.

Implement `page.tsx` as a Server Component with: sticky glassmorphism nav (logo, Features/Pricing/Sources/Docs links, Sign in + "Start free kit" buttons), hero headline + subhead + primary CTA, steps strip (01 League profile / 02 Weight sources / 03 Draft), features grid (6 items from spec 010 Claude Design), pricing section, footer.
```bash
pnpm --filter @pucklogic/web test -- src/app/__tests__/page.test.tsx 2>&1 | tail -10
```
Expected: all landing page tests pass.

---

### Wave 3 — Pre-draft workspace
*Depends on Wave 2.*

**Task 3.1 — Write failing tests for KitSwitcher**
Create `src/components/__tests__/KitSwitcher.test.tsx`. Tests: (a) renders kit names from props; (b) active kit has `aria-checked="true"` or checkmark; (c) "New kit" button is present; (d) each kit row has overflow menu trigger.
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/KitSwitcher.test.tsx 2>&1 | tail -10
```
Expected: fails — module not found.

**Task 3.2 — Create `src/store/slices/kits.ts` and wire into `store/index.ts`**
State: `kits: UserKit[]`, `activeKitId: string | null`. Actions: `setKits(kits)`, `setActiveKit(id)`, `addKit(kit)`, `removeKit(id)`, `updateKit(id, patch)`. Add `createKitsSlice` to `store/index.ts` with the existing `createSourcesSlice` + `createRankingsSlice`.
```bash
pnpm --filter @pucklogic/web test -- src/store/__tests__/kits.slice.test.ts 2>&1 | tail -10
```
Expected: all kits slice tests pass.

**Task 3.3 — Create `src/lib/api/entitlements.ts`**
Exports `fetchEntitlements(token: string): Promise<{ kit_pass: boolean; draft_passes: number }>` — calls `apiFetch('/entitlements', { token })`.
```bash
pnpm --filter @pucklogic/web test -- src/lib/api/__tests__/entitlements.test.ts 2>&1 | tail -10
```
Expected: entitlements client tests pass (vi.spyOn apiFetch).

**Task 3.4 — Verify and complete `src/lib/api/user-kits.ts`**
Ensure exports: `listKits(token)`, `createKit(payload, token)`, `updateKit(id, patch, token)`, `deleteKit(id, token)`, `duplicateKit(id, token)` — all via `apiFetch`. Add or update `__tests__/user-kits.test.ts`.
```bash
pnpm --filter @pucklogic/web test -- src/lib/api/__tests__/user-kits.test.ts 2>&1 | tail -10
```
Expected: all user-kits API tests pass.

**Task 3.5 — Create `src/components/KitSwitcher.tsx` and make tests pass**
`'use client'`. Right slide-in panel with scrim (same motion spec as spec 010: 260ms cubic-bezier). Reads `kits` and `activeKitId` from `useStore`. Kit cards: click → `setActiveKit(id)` + `onClose()`. Active kit has checkmark icon. Overflow menu per card: Rename (inline edit), Duplicate (calls `duplicateKit` API + `addKit` dispatch), Delete (confirm then `deleteKit` API + `removeKit` dispatch). "New kit" inline form: name input → submit → `createKit` API → `addKit` dispatch → `setActiveKit`.
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/KitSwitcher.test.tsx 2>&1 | tail -10
```
Expected: all KitSwitcher tests pass.

**Task 3.6 — Write failing tests for PreDraftWorkspace**
Create `src/components/__tests__/PreDraftWorkspace.test.tsx`. Tests: (a) `RankingsTable` is rendered; (b) right panel contains source weight sliders; (c) "Export rankings" button present; (d) "Export draft sheet" button present.
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/PreDraftWorkspace.test.tsx 2>&1 | tail -10
```
Expected: fails — module not found.

**Task 3.7 — Create `src/components/PreDraftWorkspace.tsx` and make tests pass**
Accepts: `rankings: RankedPlayer[]`, `sources: Source[]`, `weights: Record<string, number>`, `onCompute: () => void`. Renders: position filter pill row (All/C/LW/RW/D/G), `<RankingsTable>` (existing), right panel with `<SourceWeightSelector>` (existing), league profile placeholder ("No league configured — Add league"), export buttons. Right panel is persistent desktop; spec 010 mobile drawer is out of scope.
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/PreDraftWorkspace.test.tsx 2>&1 | tail -10
```
Expected: all PreDraftWorkspace tests pass.

**Task 3.8 — Refactor `src/app/(auth)/dashboard/page.tsx` to Server Component using PreDraftWorkspace**
The current file is `'use client'` with `useState`, `useEffect`, `useStore`, and inline API calls. This is a near-rewrite, not a wrapper swap. Steps:

1. Delete `'use client'` directive at line 1
2. Remove all imports of `useState`, `useEffect`, `useStore`
3. Convert `export default function` to `export default async function`
4. Fetch data server-side: `const { data: { session } } = await supabase.auth.getSession()`, then `fetchSources(session.access_token)` and `computeRankings(...)` 
5. Replace all inline JSX with `<PreDraftWorkspace rankings={rankings} sources={sources} weights={defaultWeights} onCompute={...} />`
6. Verify no client hooks remain:
```bash
grep -n "useState\|useEffect\|useStore\|'use client'" apps/web/src/app/\(auth\)/dashboard/page.tsx
```
Expected: no matches.
```bash
pnpm --filter @pucklogic/web build 2>&1 | tail -5
```
Expected: exits 0; no type errors.

**Task 3.9 — Create login and signup pages**
These pages must be outside the `(auth)` route group — placing them inside would cause `(auth)/layout.tsx` to redirect unauthenticated users to `/login` while `/login` itself redirects again, creating an infinite loop.

`src/app/login/page.tsx` (`'use client'`): email + password form; `supabase.auth.signInWithPassword({ email, password })`; on success `router.push('/dashboard')`; on error show inline error message.

`src/app/signup/page.tsx` (`'use client'`): email + password + confirm-password form; `supabase.auth.signUp({ email, password, options: { emailRedirectTo: '/auth/callback' } })`; on success show "Check your email to confirm your account".
```bash
pnpm --filter @pucklogic/web test -- src/app/__tests__/auth-pages.test.tsx 2>&1 | tail -10
```
Expected: login + signup render tests pass.

**Task 3.10 — Create `src/app/auth/callback/route.ts`**
GET route handler. Read `code` from `searchParams`. Call `supabase.auth.exchangeCodeForSession(code)`. On success: `redirect('/dashboard')` — the full navigation to `/dashboard` triggers `(auth)/layout.tsx` to re-run on the server, which re-fetches entitlements (F-1 satisfied). On error: `redirect('/login?error=auth_callback_failed')`.
```bash
pnpm --filter @pucklogic/web build 2>&1 | tail -5
```
Expected: TypeScript compiles; route handler type-safe.

---

### Wave 4 — Session API + state
*Depends on Wave 3.*

**Task 4.1 — Write failing tests for draft-sessions API client**
Create `src/lib/api/__tests__/draft-sessions.test.ts`. Tests (all mock `apiFetch` via `vi.spyOn`): (a) `createSession` POSTs to `/draft-sessions/start`; (b) `resumeSession` POSTs to `/draft-sessions/{id}/resume`; (c) `recordPick` POSTs to `/draft-sessions/{id}/manual-picks` with pick payload; (d) `endSession` POSTs to `/draft-sessions/{id}/end`; (e) `fetchSyncState` GETs `/draft-sessions/{id}/sync-state`.
```bash
pnpm --filter @pucklogic/web test -- src/lib/api/__tests__/draft-sessions.test.ts 2>&1 | tail -10
```
Expected: fails — module not found.

**Task 4.2 — Create `src/lib/api/draft-sessions.ts`**
Exports (all paths verified against `apps/api/routers/draft_sessions.py`):
- `createSession(payload: { kitId: string; espnLeagueId?: string }, token: string)` → POST `/draft-sessions/start`
- `resumeSession(sessionId: string, token: string)` → POST `/draft-sessions/${sessionId}/resume`
- `recordPick(sessionId: string, pick: { playerId: string; round: number; pickNumber: number }, token: string)` → POST `/draft-sessions/${sessionId}/manual-picks`
- `endSession(sessionId: string, token: string)` → POST `/draft-sessions/${sessionId}/end`
- `fetchSyncState(sessionId: string, token: string)` → GET `/draft-sessions/${sessionId}/sync-state`
```bash
pnpm --filter @pucklogic/web test -- src/lib/api/__tests__/draft-sessions.test.ts 2>&1 | tail -10
```
Expected: all draft-sessions API tests pass.

**Task 4.3 — Write failing tests for draftSession Zustand slice**
Create `src/store/__tests__/draftSession.slice.test.ts`. Tests: (a) `startSession({ sessionId, kitId })` sets `status: 'active'`, `sessionId`; (b) `recordPick(pick)` appends to `picks`; (c) `setMode('manual')` updates `mode`; (d) `endSession()` sets `status: 'ended'`; (e) `reset()` returns to initial state.
```bash
pnpm --filter @pucklogic/web test -- src/store/__tests__/draftSession.slice.test.ts 2>&1 | tail -10
```
Expected: fails — module not found.

**Task 4.4 — Create `src/store/slices/draftSession.ts` and wire into `store/index.ts`**
State: `sessionId: string | null`, `kitId: string | null`, `picks: DraftPick[]`, `mode: 'sync' | 'manual' | 'reconnecting' | 'disconnected'`, `status: 'idle' | 'active' | 'ended'`. Actions: `startSession`, `recordPick`, `setMode`, `endSession`, `reset`. Add `createDraftSessionSlice` to `store/index.ts`.

Add `DraftPick` type to `src/types/index.ts`: `{ playerId: string; playerName: string; round: number; pickNumber: number; recordedAt: string }`.
```bash
pnpm --filter @pucklogic/web test -- src/store/__tests__/draftSession.slice.test.ts 2>&1 | tail -10
```
Expected: all draftSession slice tests pass.

**Task 4.5 — Create session-start flow: cookie write + store dispatch + navigation**
This is the client-side handler that glues session creation to the live route. Without it, `live/page.tsx` cannot read the `sessionId` server-side (Task 5.5 pre-condition).

Create `src/components/StartDraftModal.tsx` (`'use client'`). Props: `kitId: string`, `onClose: () => void`. Renders the "Start live draft" confirmation modal (Claude Design: draft pass confirmation, ESPN connected/not-installed variants, "Start without sync" fallback). On confirm:
1. Call `createSession({ kitId }, token)` — POST `/draft-sessions/start`
2. Write `document.cookie = \`draft-session-id=${response.session_id}; path=/; SameSite=Lax\`` so `live/page.tsx` Server Component can read it
3. Dispatch `startSession({ sessionId: response.session_id, kitId })` to Zustand
4. Call `router.push('/live')`

Add `src/components/__tests__/StartDraftModal.test.tsx`. Tests: (a) renders confirmation text and confirm button; (b) on confirm, calls `createSession`; (c) on success, `router.push` is called with `/live`.
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/StartDraftModal.test.tsx 2>&1 | tail -10
```
Expected: all StartDraftModal tests pass.

---

### Wave 5 — Live draft screen
*Depends on Wave 4.*

**Task 5.1 — Write failing tests for ReconnectBanner, ManualPickDrawer, LiveDraftScreen**
Create three test files. ReconnectBanner: renders when `mode === 'reconnecting'`; hidden when `mode === 'sync'`; "Switch to manual" button calls `setMode('manual')`. ManualPickDrawer: search input present; selecting a row enables confirm button; confirm button triggers `onConfirm` callback; "Recorded" text appears after confirm. LiveDraftScreen: renders "Available players" heading; renders at least one suggestion card; renders "Roster needs" heading; renders sync status indicator.
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/ReconnectBanner.test.tsx src/components/__tests__/ManualPickDrawer.test.tsx src/components/__tests__/LiveDraftScreen.test.tsx 2>&1 | tail -10
```
Expected: all three fail — modules not found.

**Task 5.2 — Create `src/components/ReconnectBanner.tsx` and make its tests pass**
`'use client'`. Reads `mode` from `useStore`. Renders a fixed top banner when `mode === 'reconnecting' || mode === 'disconnected'`. "Switch to manual" button dispatches `setMode('manual')`. Returns `null` when `mode === 'sync' || mode === 'manual'`. Motion: opacity 220ms ease (spec 010).
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/ReconnectBanner.test.tsx 2>&1 | tail -10
```
Expected: all ReconnectBanner tests pass.

**Task 5.3 — Create `src/components/ManualPickDrawer.tsx` and make its tests pass**
`'use client'`. Props: `open: boolean`, `onClose: () => void`, `onConfirm: (pick: { playerId: string; round: number; pickNumber: number }) => void`. Right slide-in panel (260ms cubic-bezier). Round + pick selectors. Player search input with live `useMemo` filter over `players` prop. Scrollable results list with selection state. Confirm button: enabled only when player selected; on click calls `onConfirm` then shows "Recorded" flash for 700ms before calling `onClose`.
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/ManualPickDrawer.test.tsx 2>&1 | tail -10
```
Expected: all ManualPickDrawer tests pass.

**Task 5.4 — Create `src/components/LiveDraftScreen.tsx` and make its tests pass**
`'use client'`. Reads `picks`, `mode`, `sessionId` from `useStore`. Props: `players: RankedPlayer[]`, `myTeamPlayers: RankedPlayer[]`. Two-column layout: left = position filter pills + available players table (filters out already-picked players by `picks`); right panel = suggestion stack (3 cards: priority/alt/sleeper, each showing player + position + score + roster-need label), roster needs grid (per position: filled/needed, color-coded), my team list (picks in round order), sync status bar (mode indicator + "+ Manual pick" button that opens `<ManualPickDrawer>`).
```bash
pnpm --filter @pucklogic/web test -- src/components/__tests__/LiveDraftScreen.test.tsx 2>&1 | tail -10
```
Expected: all LiveDraftScreen tests pass.

**Task 5.5 — Create `src/app/(auth)/live/layout.tsx` and `src/app/(auth)/live/page.tsx`**
`layout.tsx`: renders `<ReconnectBanner />` above `{children}`; no kit context bar.

`page.tsx`: Server Component. Note: `/draft-sessions/active` does not exist in the backend. Instead, the `sessionId` is written to Zustand store by the "Start live draft" flow before navigation to `/live`. The page reads `sessionId` from a server-readable cookie (`draft-session-id`) set during session creation. If the cookie is absent → `redirect('/dashboard')`. If present, call `fetchSyncState(sessionId, token)` (GET `/draft-sessions/{id}/sync-state`) to hydrate initial sync state, then fetch ranked players and render `<LiveDraftScreen players={...} myTeamPlayers={...} initialSyncState={syncState} />`.
```bash
pnpm --filter @pucklogic/web build 2>&1 | tail -5
```
Expected: TypeScript compiles; no import errors.

**Task 5.6 — Full verification pass**
```bash
pnpm --filter @pucklogic/web test && pnpm --filter @pucklogic/web build
```
Expected: all 22+ AC tests pass; production build exits 0.

---

## Adversarial Plan Review

**Packet:** `docs/plans/010a-adversarial-review-r1.md`
**Round:** 1
**Verdict:** `BLOCKED` → corrections applied → `APPROVED WITH NITS` (pending round 2 external review)
**Corrections applied:**
- F-1: Login/signup moved outside `(auth)` route group (infinite redirect loop)
- F-2: Middleware uses actual URL path matching, not `(auth)/**` route-group syntax
- F-3: All draft session API endpoints corrected to match backend; `fetchSyncState` added
- F-4: Task 3.8 expanded with explicit hook-removal steps for client→server refactor
- F-5: Task 5.5 replaced `/draft-sessions/active` (non-existent) with cookie-based sessionId + `fetchSyncState`

**Final verdict:** `APPROVED WITH NITS` — all findings resolved including residual cookie write (Task 4.5 / AC-23). F-7 (middleware mock complexity) accepted as minor known risk.

**Adversarial PR/QA review required downstream:** Yes — specifically:
- `middleware.ts` (route protection, redirect rules)
- `(auth)/layout.tsx` (entitlements fetch, UserProvider wiring, server component auth gate)
- `auth/callback/route.ts` (PKCE exchange, session handling — auth surface)
- `StartDraftModal.tsx` (session creation + cookie write — auth surface)

---

## Risks

- **Route migration (Task 2.7):** Moving `dashboard/` into `(auth)/dashboard/` changes any hardcoded `/dashboard` hrefs in existing components. Scan for these before the move.
- **shadcn token surface growth:** If additional shadcn components are added during implementation, they may read shadcn tokens not yet bridged in Wave 1 `globals.css`. Check token completeness against each `npx shadcn@latest add` call.
- **draftSession hydration gap:** Zustand picks list is client-side only. Hard refresh during a live session loses local state. Session hydration from backend on page load is not in this plan — deferred to a follow-up.
- **`user-kits.ts` audit (Task 3.4):** The file exists but was not fully audited in research doc 003. If the CRUD methods are missing or type-incorrect, Task 3.4 may take longer than estimated.
