# 008d Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status update — 2026-04-25:** Implemented on PR #34 / branch `feat/008d-draft-pass-session-lifecycle`. The targeted remediation scope landed, including the migration uniqueness fix, terminal-session handling across HTTP + WS paths, extension reconnect suppression keyed off `SESSION_CLOSED`, and the final `/end` HTTP 409 follow-up. This document is retained as the historical execution checklist.

**Goal:** Fix five issues from two code reviews on PR #34: a runtime SQL error in `credit_draft_pass_for_stripe_event`, missing terminal-session check in `accept_pick`, missing socket-close on in-loop WS terminal errors, overlapping sockets on repeated `initSession`, and brittle string-coupled terminal denial.

**Architecture:** Five targeted fixes, no structural changes. (1) Migration 008 gains a `UNIQUE` constraint on `subscriptions.user_id` and drops a redundant index already created in 006. (2) `accept_pick` gets a `_raise_if_terminal` call before its generic `LookupError`. (3) The WS `pick` and `sync_state` in-loop handlers catch `TerminalSessionError` separately and close the socket. (4) `BackgroundSessionBridge.initSession()` cancels the previous socket's reconnect loop via a per-connection `cancelled` closure before opening a fresh socket. (5) Terminal denial WS errors gain a stable `code: "SESSION_CLOSED"` field; the extension keys off the code, not the message string.

**Tech Stack:** PostgreSQL/Supabase migrations, Python 3.11, FastAPI, pytest, TypeScript, Vitest

---

## File Surface

| Action | File | Change |
|--------|------|--------|
| Modify | `supabase/migrations/008_draft_session_lifecycle.sql` | Add `UNIQUE (user_id)` constraint; remove redundant index already in migration 006 |
| Modify | `apps/api/services/draft_sessions.py` | Add `_raise_if_terminal` call in `accept_pick` |
| Modify | `apps/api/routers/draft_sessions.py` | Catch `TerminalSessionError` before `LookupError` in WS `pick` and `sync_state` handlers; add `code: SESSION_CLOSED` to all terminal denial payloads |
| Modify | `apps/api/tests/services/test_draft_sessions.py` | Add `TestAcceptPickTerminalSession` class |
| Modify | `apps/api/tests/routers/test_draft_sessions.py` | Add `TestWebSocketTerminalInLoop` class; update terminal denial assertions to check `code` field |
| Modify | `packages/extension/src/background/index.ts` | Add `_cancelCurrentReconnect` closure to `connect()`; update `initSession()` to cancel old socket; update `onmessage` to key off `payload.code` |
| Modify | `packages/extension/src/__tests__/background.test.ts` | Add repeated-init tests; update `triggerMessage` calls to include `code: "SESSION_CLOSED"` |

---

## Task 1: Fix migration 008 — add UNIQUE constraint and remove redundant index

Migration 008 has not been applied to any database yet. Edit it in place.

**Files:**
- Modify: `supabase/migrations/008_draft_session_lifecycle.sql`

- [ ] **Step 1: Add the UNIQUE constraint and remove the duplicate index**

  Open `supabase/migrations/008_draft_session_lifecycle.sql`. Make two edits:

  **Schema ordering:** Supabase applies migrations in lexicographic filename order. `006_...` always precedes `008_...`. Migration 006 creates `draft_sessions_one_active_per_user_idx` with `IF NOT EXISTS`, so it is guaranteed to exist when 008 runs. No ordering risk.

  **Constraint syntax note:** `ALTER TABLE ADD CONSTRAINT IF NOT EXISTS` is NOT valid PostgreSQL syntax — only `ADD COLUMN` supports `IF NOT EXISTS`. Use `CREATE UNIQUE INDEX IF NOT EXISTS` instead. PostgreSQL's `ON CONFLICT (user_id)` resolves against unique indexes (not only constraints), so this achieves the same result with safe, idiomatic syntax supported since PostgreSQL 9.5.

  **Edit A** — After the `alter table subscriptions add column if not exists draft_pass_balance ...` block (currently ending around line 15) and before the `create table if not exists stripe_processed_events` block, insert a dedupe step followed by the unique index:

  ```sql
  -- Deduplicate subscriptions per user before adding the unique index.
  -- Expected to be a no-op in pre-launch deployments (no real payments processed yet).
  -- In the unlikely event duplicates exist (from concurrent credit_draft_pass() non-atomic
  -- fallback calls), keep the row with the highest draft_pass_balance.
  delete from subscriptions
  where id not in (
    select distinct on (user_id) id
    from subscriptions
    order by user_id, draft_pass_balance desc, created_at desc, id desc
  );

  -- ON CONFLICT (user_id) in credit_draft_pass_for_stripe_event requires a unique index.
  -- CREATE UNIQUE INDEX IF NOT EXISTS is idempotent; ADD CONSTRAINT has no IF NOT EXISTS form in PostgreSQL.
  create unique index if not exists subscriptions_user_id_unique
    on subscriptions (user_id);
  ```

  **Edit B** — Remove the duplicate index block (currently lines 26–28). Migration 006 already creates this index, so this is dead weight:

  ```sql
  -- DELETE these three lines:
  create unique index if not exists draft_sessions_one_active_per_user_idx
    on draft_sessions (user_id)
    where status = 'active';
  ```

  The complete top section of the file after both edits should read:

  ```sql
  -- Add completion audit fields to draft_sessions.
  -- completion_reason distinguishes user-explicit end from inactivity expiry.
  -- completed_at records when the session reached a terminal state.

  alter table draft_sessions
    add column if not exists completion_reason text
      check (completion_reason in ('user_ended', 'inactivity_expired')),
    add column if not exists completed_at timestamptz;

  -- Add per-user draft pass balance to subscriptions.
  -- Incremented by Stripe webhook on successful checkout; decremented on session start.

  alter table subscriptions
    add column if not exists draft_pass_balance integer not null default 0
      check (draft_pass_balance >= 0);

  -- Deduplicate subscriptions per user before adding the unique index.
  -- Expected to be a no-op in pre-launch deployments (no real payments processed yet).
  -- In the unlikely event duplicates exist (from concurrent credit_draft_pass() non-atomic
  -- fallback calls), keep the row with the highest draft_pass_balance.
  delete from subscriptions
  where id not in (
    select distinct on (user_id) id
    from subscriptions
    order by user_id, draft_pass_balance desc, created_at desc, id desc
  );

  -- ON CONFLICT (user_id) in credit_draft_pass_for_stripe_event requires a unique index.
  -- CREATE UNIQUE INDEX IF NOT EXISTS is idempotent; ADD CONSTRAINT has no IF NOT EXISTS form in PostgreSQL.
  create unique index if not exists subscriptions_user_id_unique
    on subscriptions (user_id);

  -- Stripe webhook idempotency guard.
  -- Processed event IDs are stored here so duplicate webhook deliveries do not
  -- double-credit the user's draft pass balance.

  create table if not exists stripe_processed_events (
      event_id   text        primary key,
      processed_at timestamptz not null default now()
  );

  create unique index if not exists draft_sessions_one_active_per_entitlement_idx
    on draft_sessions (entitlement_ref)
    where status = 'active' and entitlement_ref is not null;
  ```

  Everything from `create or replace function consume_draft_pass` onward is unchanged.

- [ ] **Step 2: Verify the file looks correct and confirm syntax compatibility**

  ```bash
  grep -n "unique\|UNIQUE\|draft_sessions_one_active_per_user_idx\|subscriptions_user_id_unique" supabase/migrations/008_draft_session_lifecycle.sql
  ```

  Expected output (approximate line numbers):
  ```
  17:create unique index if not exists subscriptions_user_id_unique
  26:create unique index if not exists draft_sessions_one_active_per_entitlement_idx
  ```

  Confirm: `draft_sessions_one_active_per_user_idx` does NOT appear; `subscriptions_user_id_unique` appears once before the functions. `CREATE UNIQUE INDEX IF NOT EXISTS` is valid PostgreSQL 9.5+ — no version caveat for Supabase PG15.

- [ ] **Step 3: Apply migration 008 against a clean schema and validate the function end-to-end**

  This is the reviewer-required validation step. The goal is to prove that after applying the migration, `credit_draft_pass_for_stripe_event` (a) credits a pass on the first event and (b) no-ops on a duplicate event.

  **Option A — Supabase CLI local dev (preferred if configured):**

  ```bash
  # Spin up a local Postgres instance with all migrations applied from scratch
  supabase start
  supabase db reset
  ```

  Then connect to the local DB:
  ```bash
  psql "postgresql://postgres:postgres@localhost:54322/postgres"
  ```

  **Option B — Supabase dashboard SQL editor** (if local dev is not configured):
  Open the Supabase dashboard → SQL Editor → run migration 008 SQL manually in a transaction first, then run the validation queries below.

  **Before applying the migration** — check for existing duplicate `user_id` rows. Run this against the target DB:

  ```sql
  select user_id, count(*) as cnt
  from subscriptions
  group by user_id
  having count(*) > 1;
  ```

  If this returns any rows, the dedupe `DELETE` in migration 008 will remove them (keeping the highest-balance row). Review those rows before proceeding so you know what data will be dropped. If the table is empty or has no duplicates, proceed immediately.

  **Validation queries** (run these after migration 008 is applied, regardless of option):

  ```sql
  -- Setup: insert a test subscription row (or reuse existing in local dev)
  insert into subscriptions (user_id, plan, status, draft_pass_balance)
  values ('00000000-0000-0000-0000-000000000001', 'draft_pass', 'active', 0);

  -- Test 1: First event should credit one pass and return true
  select credit_draft_pass_for_stripe_event(
    'evt_validate_001',
    '00000000-0000-0000-0000-000000000001'
  );
  -- Expected: true

  -- Confirm balance was incremented
  select draft_pass_balance from subscriptions
  where user_id = '00000000-0000-0000-0000-000000000001';
  -- Expected: 1

  -- Test 2: Duplicate event must be a no-op and return false
  select credit_draft_pass_for_stripe_event(
    'evt_validate_001',
    '00000000-0000-0000-0000-000000000001'
  );
  -- Expected: false

  -- Confirm balance was NOT incremented a second time
  select draft_pass_balance from subscriptions
  where user_id = '00000000-0000-0000-0000-000000000001';
  -- Expected: still 1
  ```

  If any result differs from expected, stop and diagnose before committing.

- [ ] **Step 4: Update `apps/api/CLAUDE.md` to document the one-row-per-user invariant**

  Open `apps/api/CLAUDE.md`. Find the line:
  ```
  subscriptions.py    # SubscriptionRepository — is_active(user_id)
  ```

  Replace it with:
  ```
  subscriptions.py    # SubscriptionRepository — is_active(user_id); one row per user_id (enforced by subscriptions_user_id_unique index from migration 008)
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add supabase/migrations/008_draft_session_lifecycle.sql apps/api/CLAUDE.md
  git commit -m "fix(migration): dedupe + unique index on subscriptions.user_id; document one-row-per-user invariant"
  ```

---

## Task 2: Fix `accept_pick` to check for terminal session before raising generic LookupError

**Files:**
- Modify: `apps/api/services/draft_sessions.py` (around line 203)
- Modify: `apps/api/tests/services/test_draft_sessions.py` (add class at end of file)

- [ ] **Step 1: Write the failing tests**

  Open `apps/api/tests/services/test_draft_sessions.py`. The file currently imports:

  ```python
  from services.draft_sessions import DraftSessionService
  ```

  Change that line to:

  ```python
  from services.draft_sessions import DraftSessionService, TerminalSessionError
  ```

  Then append the following class at the end of the file:

  ```python
  class TestAcceptPickTerminalSession:
      def test_accept_pick_raises_terminal_error_for_ended_session(
          self,
          service: DraftSessionService,
          mock_repo: MagicMock,
          mock_sub_repo: MagicMock,
      ) -> None:
          now = datetime.now(UTC)
          mock_repo.get_active_session.return_value = None
          mock_repo.expire_inactive_sessions.return_value = 0
          mock_repo.get_session_by_id.return_value = {
              "session_id": "ses_1",
              "user_id": "usr_1",
              "status": "ended",
              "completion_reason": "user_ended",
          }

          with pytest.raises(TerminalSessionError, match="session is closed"):
              service.accept_pick(
                  session_id="ses_1",
                  user_id="usr_1",
                  pick_number=1,
                  now=now,
              )

      def test_accept_pick_raises_terminal_error_for_expired_session(
          self,
          service: DraftSessionService,
          mock_repo: MagicMock,
          mock_sub_repo: MagicMock,
      ) -> None:
          now = datetime.now(UTC)
          mock_repo.get_active_session.return_value = None
          mock_repo.expire_inactive_sessions.return_value = 0
          mock_repo.get_session_by_id.return_value = {
              "session_id": "ses_1",
              "user_id": "usr_1",
              "status": "expired",
              "completion_reason": "inactivity_expired",
          }

          with pytest.raises(TerminalSessionError, match="session is closed"):
              service.accept_pick(
                  session_id="ses_1",
                  user_id="usr_1",
                  pick_number=1,
                  now=now,
              )

      def test_accept_pick_raises_plain_lookup_error_when_session_not_found_at_all(
          self,
          service: DraftSessionService,
          mock_repo: MagicMock,
          mock_sub_repo: MagicMock,
      ) -> None:
          now = datetime.now(UTC)
          mock_repo.get_active_session.return_value = None
          mock_repo.expire_inactive_sessions.return_value = 0
          mock_repo.get_session_by_id.return_value = None

          with pytest.raises(LookupError, match="active session not found"):
              service.accept_pick(
                  session_id="ses_nonexistent",
                  user_id="usr_1",
                  pick_number=1,
                  now=now,
              )
  ```

- [ ] **Step 2: Run to verify the tests fail**

  ```bash
  cd apps/api && pytest tests/services/test_draft_sessions.py::TestAcceptPickTerminalSession -v
  ```

  Expected: 3 FAILED — the service raises `LookupError("active session not found for user")` instead of `TerminalSessionError`.

- [ ] **Step 3: Add `_raise_if_terminal` call in `accept_pick`**

  Open `apps/api/services/draft_sessions.py`. Find lines 203–204:

  ```python
          if active is None or active.get("session_id") != session_id:
              raise LookupError("active session not found for user")
  ```

  Replace with:

  ```python
          if active is None or active.get("session_id") != session_id:
              self._raise_if_terminal(session_id, user_id)
              raise LookupError("active session not found for user")
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  cd apps/api && pytest tests/services/test_draft_sessions.py -v
  ```

  Expected: all tests pass, including the 3 new ones.

- [ ] **Step 5: Commit**

  ```bash
  git add apps/api/services/draft_sessions.py apps/api/tests/services/test_draft_sessions.py
  git commit -m "fix(service): accept_pick checks terminal state before generic LookupError"
  ```

---

## Task 3: Fix WS `pick` and `sync_state` handlers — close socket on terminal + add `SESSION_CLOSED` code

This task rewrites the WS event-loop exception handlers to (a) catch `TerminalSessionError` before the generic `LookupError` catch, (b) close the socket on terminal denial, and (c) include `code: "SESSION_CLOSED"` in the terminal denial payload. It also fixes the same code gap in the initial `attach_socket` handler so all three paths are consistent.

**Files:**
- Modify: `apps/api/routers/draft_sessions.py`
- Modify: `apps/api/tests/routers/test_draft_sessions.py` (add class; update existing assertions)

- [ ] **Step 1: Write the failing tests**

  Open `apps/api/tests/routers/test_draft_sessions.py`. `TerminalSessionError` is already imported. Append the following class at the end of the file:

  ```python
  class TestWebSocketTerminalInLoop:
      def test_pick_event_sends_session_closed_code_and_closes_socket(
          self, client: TestClient, mock_service: MagicMock
      ) -> None:
          mock_service.attach_socket.return_value = {"sync_health": "healthy"}
          mock_service.accept_pick.side_effect = TerminalSessionError("session is closed")

          with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
              ws.receive_json()  # consume initial sync_state from attach_socket
              ws.send_json({"type": "pick", "payload": {"pick_number": 1}})
              error = ws.receive_json()

          assert error["type"] == "error"
          assert error["payload"]["code"] == "SESSION_CLOSED"
          assert "closed" in error["payload"]["message"]

      def test_sync_state_event_sends_session_closed_code_and_closes_socket(
          self, client: TestClient, mock_service: MagicMock
      ) -> None:
          mock_service.attach_socket.return_value = {"sync_health": "healthy"}
          mock_service.reconnect_sync_state.side_effect = TerminalSessionError("session is closed")

          with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
              ws.receive_json()  # consume initial sync_state from attach_socket
              ws.send_json({"type": "sync_state"})
              error = ws.receive_json()

          assert error["type"] == "error"
          assert error["payload"]["code"] == "SESSION_CLOSED"
          assert "closed" in error["payload"]["message"]
  ```

  Also update the existing `test_connect_emits_session_closed_error_when_terminal` test in `TestTerminalSessionReconnectDenial` to assert the code field:

  ```python
  def test_connect_emits_session_closed_error_when_terminal(
      self, client: TestClient, mock_service: MagicMock
  ) -> None:
      mock_service.attach_socket.side_effect = TerminalSessionError("session is closed")

      with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
          event = ws.receive_json()

      assert event["type"] == "error"
      assert event["payload"]["code"] == "SESSION_CLOSED"
      assert "closed" in event["payload"]["message"]
  ```

- [ ] **Step 2: Run to verify the tests fail**

  ```bash
  cd apps/api && pytest tests/routers/test_draft_sessions.py::TestWebSocketTerminalInLoop tests/routers/test_draft_sessions.py::TestTerminalSessionReconnectDenial::test_connect_emits_session_closed_error_when_terminal -v
  ```

  Expected: all 3 FAILED — no `code` field in any payload, and in-loop handlers don't close the socket.

- [ ] **Step 3: Rewrite the WS handler in `routers/draft_sessions.py`**

  Open `apps/api/routers/draft_sessions.py`. Replace the entire `draft_session_ws` function with the following. The only logic changes are: (1) the initial exception block splits `TerminalSessionError` out to add `code`; (2) the `pick` and `sync_state` in-loop handlers add a `TerminalSessionError` catch before the generic one, with socket-close.

  ```python
  @router.websocket("/{session_id}/ws")
  async def draft_session_ws(
      websocket: WebSocket,
      session_id: str,
      token: str | None = Query(default=None),
      service: DraftSessionService = Depends(get_draft_session_service),
  ) -> None:
      await websocket.accept()

      try:
          user = await _authenticate_websocket_user(token)
          sync_state = service.attach_socket(
              session_id=session_id,
              user_id=user["id"],
              now=datetime.now(UTC),
          )
          await websocket.send_json({"type": "sync_state", "payload": sync_state})
      except TerminalSessionError as exc:
          await websocket.send_json(
              {"type": "error", "payload": {"code": "SESSION_CLOSED", "message": str(exc)}}
          )
          await websocket.close(code=1008)
          return
      except (HTTPException, PermissionError, LookupError) as exc:
          message = exc.detail if isinstance(exc, HTTPException) else str(exc)
          await websocket.send_json({"type": "error", "payload": {"message": message}})
          await websocket.close(code=1008)
          return

      while True:
          try:
              message = await websocket.receive_json()
          except WebSocketDisconnect:
              break

          event_type = message.get("type")
          if event_type == "pick":
              payload = message.get("payload") or {}
              pick_number = payload.get("pick_number")
              if not isinstance(pick_number, int) or pick_number < 1:
                  await websocket.send_json(
                      {
                          "type": "error",
                          "payload": {
                              "message": "pick event requires a positive integer pick_number"
                          },
                      }
                  )
                  continue

              try:
                  result = service.accept_pick(
                      session_id=session_id,
                      user_id=user["id"],
                      pick_number=pick_number,
                      now=datetime.now(UTC),
                      ingestion_mode="auto",
                      player_id=payload.get("player_id"),
                      player_name=payload.get("player_name"),
                      player_lookup=payload.get("player_lookup"),
                  )
              except TerminalSessionError as exc:
                  await websocket.send_json(
                      {"type": "error", "payload": {"code": "SESSION_CLOSED", "message": str(exc)}}
                  )
                  await websocket.close(code=1008)
                  return
              except (ValueError, LookupError, PermissionError) as exc:
                  await websocket.send_json(
                      {
                          "type": "error",
                          "payload": {"message": str(exc)},
                      }
                  )
                  continue

              await websocket.send_json(
                  {
                      "type": "state_update",
                      "payload": {
                          "status": "pick_received",
                          "session_id": session_id,
                          "pick_number": pick_number,
                          "sync_state": result["sync_state"],
                      },
                  }
              )
              continue

          if event_type == "sync_state":
              try:
                  sync_state = service.reconnect_sync_state(
                      session_id=session_id,
                      user_id=user["id"],
                      now=datetime.now(UTC),
                  )
              except TerminalSessionError as exc:
                  await websocket.send_json(
                      {"type": "error", "payload": {"code": "SESSION_CLOSED", "message": str(exc)}}
                  )
                  await websocket.close(code=1008)
                  return
              except (PermissionError, LookupError) as exc:
                  await websocket.send_json({"type": "error", "payload": {"message": str(exc)}})
                  continue

              await websocket.send_json({"type": "sync_state", "payload": sync_state})
              continue

          await websocket.send_json(
              {
                  "type": "error",
                  "payload": {"message": f"unsupported event type: {event_type}"},
              }
          )
  ```

- [ ] **Step 4: Run all router tests**

  ```bash
  cd apps/api && pytest tests/routers/test_draft_sessions.py -v
  ```

  Expected: all tests pass, including the 2 new `TestWebSocketTerminalInLoop` tests and the updated `test_connect_emits_session_closed_error_when_terminal`.

- [ ] **Step 5: Run the full suite to check for regressions**

  ```bash
  cd apps/api && pytest -v
  ```

  Expected: all tests pass.

- [ ] **Step 6: Commit**

  ```bash
  git add apps/api/routers/draft_sessions.py apps/api/tests/routers/test_draft_sessions.py
  git commit -m "fix(router): terminal WS denial closes socket and sends SESSION_CLOSED code across all paths"
  ```

---

## Task 4: Harden `BackgroundSessionBridge.initSession` against overlapping sockets

`initSession` currently sets `stopReconnect = false` and calls `connect()` without closing any existing socket. A second `initSession` call (e.g., user starts a new draft) leaves the old socket's reconnect loop active in parallel. Fix: use a per-connection `cancelled` closure variable. `initSession` calls `_cancelCurrentReconnect()` to freeze the old socket's loop before opening a new connection.

> **Version-compatibility note:** This task also changes the terminal denial detection in `onmessage` from `message.includes("session is closed")` to `payload.code === "SESSION_CLOSED"`. The extension will stop suppressing reconnects for backends that send the old payload shape (no `code` field). This is safe **only if backend and extension ship together** — i.e., the router changes from Task 3 and this extension change land in the same deploy. Do not release the extension independently ahead of the backend.

**Files:**
- Modify: `packages/extension/src/background/index.ts`
- Modify: `packages/extension/src/__tests__/background.test.ts`

- [ ] **Step 1: Write the failing tests**

  Open `packages/extension/src/__tests__/background.test.ts`. Append after the last `it(...)` block inside the `describe("BackgroundSessionBridge", ...)`:

  ```typescript
  it("repeated INIT_SESSION closes the old socket and opens one for the new session", async () => {
    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-reinit",
    });

    await bridge.initSession({
      sessionId: "session-1",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-1/ws",
    });
    const firstSocket = FakeWebSocket.instances[0];
    firstSocket.triggerOpen();

    await bridge.initSession({
      sessionId: "session-2",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-2/ws",
    });

    // first socket must be closed by initSession
    expect(firstSocket.readyState).toBe(FakeWebSocket.CLOSED);
    // second socket created for new session
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1].url).toContain("session-2");
  });

  it("old socket reconnect loop does not fire after repeated INIT_SESSION", async () => {
    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-reinit2",
    });

    await bridge.initSession({
      sessionId: "session-1",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-1/ws",
    });
    const firstSocket = FakeWebSocket.instances[0];
    firstSocket.triggerOpen();
    // Disconnect first socket — normally schedules a reconnect timer
    firstSocket.close();

    // Re-init before the reconnect timer fires; this should cancel the timer
    await bridge.initSession({
      sessionId: "session-2",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-2/ws",
    });

    // Two sockets so far: one per initSession call
    expect(FakeWebSocket.instances).toHaveLength(2);

    // Advance time so the old reconnect timer would have fired
    vi.advanceTimersByTime(2000);
    await vi.runAllTimersAsync();

    // Still 2 — old reconnect was cancelled
    expect(FakeWebSocket.instances).toHaveLength(2);
  });
  ```

- [ ] **Step 2: Run to verify the tests fail**

  ```bash
  cd packages/extension && npx vitest run src/__tests__/background.test.ts
  ```

  Expected: both new tests FAIL. The first fails because the old socket is not closed by `initSession`; the second fails because a third socket is created by the orphaned reconnect timer.

- [ ] **Step 3: Add the `_cancelCurrentReconnect` field and update `initSession`**

  Open `packages/extension/src/background/index.ts`. In the class body, add the new field after `private stopReconnect = false;`:

  ```typescript
  private _cancelCurrentReconnect: (() => void) | null = null;
  ```

  Replace the existing `initSession` method (lines 53–58):

  ```typescript
  async initSession(params: { sessionId: string; wsUrl: string }): Promise<void> {
    this.sessionId = params.sessionId;
    this.wsUrl = params.wsUrl;
    this.stopReconnect = false;
    await this.connect();
  }
  ```

  With:

  ```typescript
  async initSession(params: { sessionId: string; wsUrl: string }): Promise<void> {
    // Cancel any pending reconnect from the previous session before starting fresh.
    this._cancelCurrentReconnect?.();
    this.socket?.close();
    this.sessionId = params.sessionId;
    this.wsUrl = params.wsUrl;
    this.reconnectDelayMs = 1000;
    this.hasConnected = false;
    this.stopReconnect = false;
    await this.connect();
  }
  ```

- [ ] **Step 4: Update `connect()` to set and check the `cancelled` closure**

  Replace the existing `connect()` method (lines 76–138) with:

  ```typescript
  private async connect(): Promise<void> {
    if (!this.wsUrl) {
      return;
    }

    const token = await this.getToken();
    const socketUrl = token ? `${this.wsUrl}?token=${token}` : this.wsUrl;

    const socket = new this.WebSocketImpl(socketUrl);
    this.socket = socket;

    let cancelled = false;
    this._cancelCurrentReconnect = () => {
      cancelled = true;
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as {
          type?: string;
          payload?: { message?: string; code?: string };
        };
        if (message.type === "error" && message.payload?.code === "SESSION_CLOSED") {
          this.stopReconnect = true;
        }
      } catch {
        // Ignore non-JSON messages; reconnect policy only cares about structured terminal denial.
      }
    };

    socket.onopen = () => {
      this.reconnectDelayMs = 1000;
      this.onMetric({ type: "socket_attach_success" });
      this.onMetric({ type: "socket_open" });

      if (this.sessionId) {
        socket.send(JSON.stringify({ type: "sync_state", session_id: this.sessionId }));

        if (this.hasConnected) {
          this.onMetric({ type: "sync_recovery" });
        }
      }

      this.hasConnected = true;
    };

    socket.onclose = () => {
      this.socket = null;
      this.onMetric({ type: "socket_close" });

      if (this.stopReconnect || cancelled) {
        return;
      }

      const currentDelay = this.reconnectDelayMs;
      this.onMetric({ type: "socket_reconnect_attempt", detail: currentDelay });
      this.setTimeoutImpl(() => {
        if (cancelled) {
          return;
        }
        void this.connect();
      }, currentDelay);

      this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, 30_000);
    };

    socket.onerror = () => {
      this.onMetric({ type: "socket_attach_failure" });
      socket.close();
    };
  }
  ```

  Note: the `onmessage` handler has been updated here to key off `payload.code === "SESSION_CLOSED"`. This is the Task 5 extension change, co-located here to avoid editing `connect()` twice.

- [ ] **Step 5: Update the existing terminal denial test to use `code`**

  In `packages/extension/src/__tests__/background.test.ts`, find the `"does not reconnect after terminal closed-session denial"` test. Update the `triggerMessage` call from:

  ```typescript
  socket.triggerMessage({
    type: "error",
    payload: { message: "session is closed" },
  });
  ```

  To:

  ```typescript
  socket.triggerMessage({
    type: "error",
    payload: { code: "SESSION_CLOSED", message: "session is closed" },
  });
  ```

- [ ] **Step 6: Run the full extension test suite**

  ```bash
  cd packages/extension && npx vitest run src/__tests__/background.test.ts
  ```

  Expected: all tests pass, including the 2 new repeated-init tests.

- [ ] **Step 7: Commit**

  ```bash
  git add packages/extension/src/background/index.ts packages/extension/src/__tests__/background.test.ts
  git commit -m "fix(extension): cancel old socket reconnect loop on initSession; key terminal denial off code"
  ```

---

## Self-Review Checklist

**Spec / review coverage:**
- [x] Runtime SQL error in `credit_draft_pass_for_stripe_event` (ON CONFLICT without UNIQUE) → Task 1
- [x] Redundant index in migration 008 already present in migration 006 → Task 1
- [x] `accept_pick` missing `_raise_if_terminal` before generic LookupError → Task 2
- [x] WS `pick` handler not closing socket on terminal denial → Task 3
- [x] WS `sync_state` handler not closing socket on terminal denial → Task 3
- [x] All three WS terminal paths missing `code: SESSION_CLOSED` in payload → Task 3
- [x] Overlapping sockets / duplicate reconnect loops on repeated `initSession` → Task 4
- [x] Extension string-coupled terminal detection (`message.includes(...)`) → Task 4 Step 4

**Placeholder scan:** No TBDs. All code blocks are complete.

**Type consistency:**
- `TerminalSessionError` — imported in both service test file (added in Task 2 Step 1) and router test file (already present). Router file already imports it.
- `_raise_if_terminal(session_id, user_id)` — matches existing signature at `services/draft_sessions.py:289`.
- `websocket.close(code=1008)` — matches FastAPI WebSocket API, consistent with router line 149.
- `payload.code` type in extension `onmessage` updated to `{ message?: string; code?: string }`.
- `_cancelCurrentReconnect: (() => void) | null` — new private field, initialized to `null`, set in every `connect()` call.

**Execution order note:** Task 2 → Task 3 is a soft dependency, not a hard one. The router test in Task 3 can be written and run independently using mocks (the service mock can raise `TerminalSessionError` directly). However, completing Task 2 first ensures the full path is exercised end-to-end. Tasks 1 and 4 are fully independent of each other and of Tasks 2–3.

---

## Future hardening (out of scope for this branch)

- Add one integration-level migration validation test (e.g., a shell script or CI step that runs the migration SQL against a fresh schema and asserts no errors). This would have caught the `ON CONFLICT (user_id)` bug before code review.
