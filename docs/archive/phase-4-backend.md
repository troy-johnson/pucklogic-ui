# PuckLogic Phase 4 — Backend Implementation

## Browser Extension — WebSocket Draft Monitor Service

**Timeline:** August – September 2026 (Phase 4)
**Target Release:** v1.0 (September 2026)
**Reference:** `pucklogic_architecture.docx` · `docs/phase-2-backend.md` (rankings cache)

---

## Overview

Phase 4 backend builds the **real-time draft monitor WebSocket service** — session lifecycle management, ESPN pick relay, best-available suggestion engine, one-time payment gate, and the `draft_sessions` table. The extension content script relays picks detected in the ESPN DOM; the backend records them and returns ranked suggestions instantly.

**Deliverables:**
1. ✅ WebSocket endpoint (`/ws/draft/{session_id}`)
2. ✅ Draft session lifecycle (create, pick, undo, end)
3. ✅ Best-available suggestion engine (uses Phase 2 cached rankings)
4. ✅ `draft_sessions` table schema + DB operations
5. ✅ One-time draft session payment gate (Stripe PaymentIntent)
6. ✅ `POST /api/draft/create-session` REST endpoint
7. ✅ Test coverage (pytest + WebSocket test client)

---

## 1. Database

### 1.1 `draft_sessions` Table

The stub table created in Phase 1 is now fully populated:

```sql
-- Already created in Phase 1 migration; no new migration needed.
-- Reference: supabase/migrations/001_initial_schema.sql

-- RLS: users can read/write only their own draft sessions (already defined in Phase 1)
-- CREATE POLICY "users_own_sessions" ON draft_sessions FOR ALL USING (auth.uid() = user_id);
```

**Column reference:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Session primary key |
| `user_id` | UUID | Owner (FK → `auth.users`) |
| `league_config` | JSONB | `{rounds, teams, format, scoring_settings}` |
| `picks` | JSONB | Array of `{round, pick, player_id, player_name, team_idx}` |
| `available` | JSONB | Player IDs not yet picked (`null` = all players available) |
| `status` | TEXT | `active` \| `completed` \| `abandoned` |
| `stripe_payment_intent_id` | TEXT | Verified Stripe PaymentIntent ID |
| `started_at` | TIMESTAMPTZ | Session creation time |
| `completed_at` | TIMESTAMPTZ | When all rounds are done |
| `updated_at` | TIMESTAMPTZ | Last mutation time |

---

## 2. WebSocket Endpoint

**Location:** `apps/api/src/routers/draft.py`

### 2.1 Message Protocol

All messages are JSON-encoded.

**Client → Server:**

| `type` | Payload | Description |
|--------|---------|-------------|
| `pick` | `{player_id, player_name, round, pick}` | Record a pick |
| `undo_pick` | — | Remove the last pick |
| `get_suggestions` | `{position_need?}` | Request best-available list |
| `ping` | — | Keep-alive |

**Server → Client:**

| `type` | Payload | Description |
|--------|---------|-------------|
| `session_state` | `{session: DraftSession}` | Full session snapshot |
| `suggestions` | `{players: [BestAvailablePlayer]}` | Top available players |
| `pick_confirmed` | `{player, remaining}` | Pick recorded acknowledgement |
| `error` | `{message}` | Validation or server error |
| `pong` | — | Keep-alive response |

### 2.2 WebSocket Handler

```python
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter
from src.ws.manager import DraftConnectionManager
from src.services.draft import DraftSessionService

router = APIRouter()
manager = DraftConnectionManager()


@router.websocket("/ws/draft/{session_id}")
async def draft_websocket(websocket: WebSocket, session_id: str):
    """
    Validates session ownership, then enters the message loop.
    Authentication: Supabase JWT passed as query param `?token=<jwt>`
    """
    token = websocket.query_params.get("token")
    user_id = await verify_jwt(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    session = await DraftSessionService().get_session(session_id)
    if not session or session.user_id != user_id:
        await websocket.close(code=4003)
        return

    await manager.connect(websocket, session_id)

    # Send initial session state
    await manager.send(session_id, {"type": "session_state", "session": session.model_dump()})

    try:
        while True:
            data = await websocket.receive_json()
            await handle_message(websocket, session_id, user_id, data)
    except WebSocketDisconnect:
        manager.disconnect(session_id)


async def handle_message(ws: WebSocket, session_id: str, user_id: str, data: dict):
    service = DraftSessionService()
    msg_type = data.get("type")

    if msg_type == "pick":
        session = await service.process_pick(
            session_id,
            player_id=data["player_id"],
            player_name=data.get("player_name"),
            round=data["round"],
            pick=data["pick"],
        )
        await manager.send(session_id, {
            "type": "pick_confirmed",
            "player": {"player_id": data["player_id"], "player_name": data.get("player_name")},
            "remaining": len(session.available or []),
        })

    elif msg_type == "undo_pick":
        session = await service.undo_pick(session_id)
        await manager.send(session_id, {"type": "session_state", "session": session.model_dump()})

    elif msg_type == "get_suggestions":
        suggestions = await service.get_suggestions(
            session_id,
            position_need=data.get("position_need"),
        )
        await manager.send(session_id, {
            "type": "suggestions",
            "players": [s.model_dump() for s in suggestions],
        })

    elif msg_type == "ping":
        await manager.send(session_id, {"type": "pong"})

    else:
        await manager.send(session_id, {"type": "error", "message": f"Unknown message type: {msg_type}"})
```

### 2.3 Connection Manager

**Location:** `apps/api/src/ws/manager.py`

```python
from fastapi import WebSocket


class DraftConnectionManager:
    """Manages one active WebSocket per draft session."""

    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self.active[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        self.active.pop(session_id, None)

    async def send(self, session_id: str, message: dict) -> None:
        ws = self.active.get(session_id)
        if ws:
            await ws.send_json(message)
```

---

## 3. Draft Session Service

**Location:** `apps/api/src/services/draft.py`

```python
from src.repositories.draft import DraftRepository
from src.repositories.rankings import RankingsRepository
from src.models.draft import DraftSession, BestAvailablePlayer


class DraftSessionService:
    def __init__(self):
        self.repo = DraftRepository()
        self.rankings_repo = RankingsRepository()

    async def get_session(self, session_id: str) -> DraftSession | None:
        return await self.repo.get(session_id)

    async def process_pick(
        self,
        session_id: str,
        player_id: str,
        player_name: str | None,
        round: int,
        pick: int,
    ) -> DraftSession:
        """Records a pick and removes the player from the available pool."""
        session = await self.repo.get(session_id)
        picks = session.picks or []
        picks.append({"round": round, "pick": pick, "player_id": player_id, "player_name": player_name})

        available = session.available or []
        if player_id in available:
            available.remove(player_id)

        return await self.repo.update(session_id, {"picks": picks, "available": available})

    async def undo_pick(self, session_id: str) -> DraftSession:
        """Removes the most recent pick and restores the player to available."""
        session = await self.repo.get(session_id)
        picks = session.picks or []
        if not picks:
            return session

        last_pick = picks.pop()
        available = session.available or []
        if last_pick["player_id"] not in available:
            available.append(last_pick["player_id"])

        return await self.repo.update(session_id, {"picks": picks, "available": available})

    async def get_suggestions(
        self,
        session_id: str,
        position_need: str | None = None,
        limit: int = 10,
    ) -> list[BestAvailablePlayer]:
        """
        Returns top available players sorted by:
        1. fantasy_pts (from Phase 2 cached rankings)
        2. Optional position_need filter
        3. Breakout score bonus (Layer 1 trends, if available)
        """
        session = await self.repo.get(session_id)
        picked_ids = {p["player_id"] for p in (session.picks or [])}

        all_players = await self.rankings_repo.get_cached_rankings(
            user_kit_id=session.league_config.get("kit_id"),
            season=session.league_config.get("season", "2025-26"),
        )

        available = [
            p for p in all_players
            if p.player_id not in picked_ids
            and (position_need is None or p.position == position_need)
        ]

        # Sort: fantasy_pts descending, breakout_score as tiebreaker
        available.sort(key=lambda p: (p.fantasy_pts, p.breakout_score or 0), reverse=True)
        return available[:limit]

    async def end_session(self, session_id: str) -> DraftSession:
        """Marks the session as completed."""
        return await self.repo.update(session_id, {
            "status": "completed",
            "completed_at": "now()",
        })
```

---

## 4. REST Endpoint — Create Session

**Location:** `apps/api/src/routers/draft.py`

```python
@router.post("/api/draft/create-session")
async def create_draft_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Verifies Stripe PaymentIntent, then creates a draft session.
    Returns: { session_id, ws_url }
    """
    # Verify payment
    intent = stripe.PaymentIntent.retrieve(body.payment_intent_id)
    if intent.status != "succeeded":
        raise HTTPException(status_code=402, detail="Payment not confirmed")
    if intent.metadata.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Payment does not belong to this user")

    session = await DraftSessionService().create_session(
        user_id=current_user.id,
        league_config=body.league_config,
        payment_intent_id=body.payment_intent_id,
    )

    ws_url = f"wss://{settings.API_HOST}/ws/draft/{session.id}"
    return {"session_id": session.id, "ws_url": ws_url}
```

**Request body:**
```json
{
  "payment_intent_id": "pi_xxx",
  "league_config": {
    "rounds": 13,
    "teams": 10,
    "format": "snake",
    "season": "2025-26",
    "kit_id": "<user_kit_uuid>",
    "scoring_settings": { ... }
  }
}
```

**Stripe PaymentIntent metadata** (set at checkout time on the web app):
```json
{ "user_id": "<supabase_uid>", "product": "draft_session" }
```

---

## 5. ESPN Pick Relay Architecture

The backend does **not** scrape ESPN directly. The flow is:

```
ESPN DOM (pick happens)
  → content-script.ts (MutationObserver detects pick)
  → chrome.runtime.sendMessage({ type: 'PICK_DETECTED', ... })
  → service-worker.ts
  → WebSocket → /ws/draft/{session_id}
  → DraftSessionService.process_pick()
  → DraftSessionService.get_suggestions()
  → WebSocket response → service-worker.ts
  → chrome.runtime.sendMessage({ type: 'WS_MESSAGE', ... })
  → extension popup (renders suggestions)
```

The backend treats every `pick` message as authoritative. If the extension's DOM observer misses a pick (ESPN UI change), the user can submit picks manually via the extension's manual entry fallback — these are relayed through the same WebSocket `pick` message.

---

## 6. Testing

### 6.1 Test Structure

```
apps/api/tests/
  routers/
    test_draft_ws.py          # WebSocket test client, full pick flow
    test_draft_rest.py        # POST /api/draft/create-session, Stripe gate
  services/
    test_draft.py             # process_pick, undo_pick, get_suggestions
  ws/
    test_manager.py           # connect/disconnect/send
```

### 6.2 Key Test Cases

```python
# tests/services/test_draft.py

@pytest.mark.asyncio
async def test_process_pick_removes_from_available(mock_repo, mock_rankings):
    """Picked player is removed from available pool."""
    mock_repo.get.return_value = DraftSession(
        id="s1", user_id="u1",
        league_config={}, picks=[], available=["p1", "p2", "p3"],
        status="active",
    )
    service = DraftSessionService()
    session = await service.process_pick("s1", "p1", "Player One", round=1, pick=1)
    assert "p1" not in session.available

@pytest.mark.asyncio
async def test_undo_pick_restores_to_available(mock_repo):
    """Undone pick's player returns to available pool."""
    mock_repo.get.return_value = DraftSession(
        id="s1", user_id="u1",
        league_config={}, picks=[{"player_id": "p1", "round": 1, "pick": 1}],
        available=["p2", "p3"], status="active",
    )
    service = DraftSessionService()
    session = await service.undo_pick("s1")
    assert "p1" in session.available
    assert len(session.picks) == 0

@pytest.mark.asyncio
async def test_get_suggestions_excludes_picked_players(mock_repo, mock_rankings):
    """Suggestions do not include already-picked players."""
    mock_repo.get.return_value = DraftSession(
        id="s1", user_id="u1",
        league_config={"kit_id": "k1", "season": "2025-26"},
        picks=[{"player_id": "p1", "round": 1, "pick": 1}],
        available=None, status="active",
    )
    mock_rankings.return_value = [
        BestAvailablePlayer(player_id="p1", fantasy_pts=50, position="C"),
        BestAvailablePlayer(player_id="p2", fantasy_pts=45, position="LW"),
    ]
    service = DraftSessionService()
    suggestions = await service.get_suggestions("s1")
    assert all(s.player_id != "p1" for s in suggestions)

@pytest.mark.asyncio
async def test_get_suggestions_position_filter(mock_repo, mock_rankings):
    """position_need filter returns only matching position."""
    # ... setup with mixed positions
    suggestions = await service.get_suggestions("s1", position_need="D")
    assert all(s.position == "D" for s in suggestions)


# tests/routers/test_draft_rest.py

def test_create_session_rejects_unpaid_intent(mock_stripe, client):
    mock_stripe.PaymentIntent.retrieve.return_value = MagicMock(status="requires_payment_method")
    resp = client.post("/api/draft/create-session", json={
        "payment_intent_id": "pi_xxx",
        "league_config": {},
    }, headers=auth_headers)
    assert resp.status_code == 402

def test_create_session_succeeds_with_paid_intent(mock_stripe, mock_service, client):
    mock_stripe.PaymentIntent.retrieve.return_value = MagicMock(
        status="succeeded",
        metadata={"user_id": TEST_USER_ID},
    )
    mock_service.create_session.return_value = DraftSession(id="s1", ...)
    resp = client.post("/api/draft/create-session", json={...}, headers=auth_headers)
    assert resp.status_code == 200
    assert "session_id" in resp.json()
    assert "ws_url" in resp.json()


# tests/routers/test_draft_ws.py

@pytest.mark.asyncio
async def test_websocket_pick_flow(async_client):
    """Full pick → suggestion cycle over WebSocket."""
    async with async_client.websocket_connect("/ws/draft/s1?token=valid_jwt") as ws:
        # Server sends initial session state
        msg = await ws.receive_json()
        assert msg["type"] == "session_state"

        # Client sends a pick
        await ws.send_json({"type": "pick", "player_id": "p1", "round": 1, "pick": 1})
        msg = await ws.receive_json()
        assert msg["type"] == "pick_confirmed"

        # Client requests suggestions
        await ws.send_json({"type": "get_suggestions"})
        msg = await ws.receive_json()
        assert msg["type"] == "suggestions"
        assert all(p["player_id"] != "p1" for p in msg["players"])
```

---

## Appendix: Key Files

```
apps/api/
  src/
    routers/
      draft.py                    # WebSocket /ws/draft/{id} + POST /api/draft/create-session
    services/
      draft.py                    # DraftSessionService
    repositories/
      draft.py                    # DraftRepository (Supabase CRUD)
    ws/
      manager.py                  # DraftConnectionManager
    models/
      draft.py                    # DraftSession, BestAvailablePlayer Pydantic models
  tests/
    routers/
      test_draft_ws.py
      test_draft_rest.py
    services/
      test_draft.py
    ws/
      test_manager.py
```

### Environment Variables (Phase 4 additions)

```bash
# apps/api/.env
STRIPE_SECRET_KEY=sk_live_xxx
API_HOST=api.pucklogic.com   # used to construct wss:// URL in create-session response
```
