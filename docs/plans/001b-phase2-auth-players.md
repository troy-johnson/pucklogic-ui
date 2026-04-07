# Phase 2 Auth Router + Players API Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `POST /auth/{register,login,logout,refresh}` + `GET /auth/me` endpoints and `GET /players` + `GET /players/{id}` endpoints to the FastAPI backend.

**Architecture:** Auth router is a thin wrapper around Supabase Auth client methods — no custom token storage. Players router delegates entirely to the existing `PlayerRepository`. All new schemas are added to `models/schemas.py`.

**Tech Stack:** FastAPI, supabase-py (auth methods), pytest + MagicMock

---

## Files

| Action | Path |
|--------|------|
| Modify | `apps/api/models/schemas.py` — add auth + player schemas |
| Create | `apps/api/routers/auth.py` |
| Create | `apps/api/routers/players.py` |
| Modify | `apps/api/core/dependencies.py` — add `get_player_repository` |
| Modify | `apps/api/main.py` — register auth + players routers |
| Create | `apps/api/tests/routers/test_auth.py` |
| Create | `apps/api/tests/routers/test_players.py` |

---

## Chunk 1: Schemas + Players Router

### Task 1: Add Player and Auth schemas to models/schemas.py

**Files:**
- Modify: `apps/api/models/schemas.py`

- [ ] **Step 1: Append player and auth schemas**

Add to the end of `apps/api/models/schemas.py`:

```python
# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


class PlayerOut(BaseModel):
    id: str
    name: str
    team: str | None = None
    position: str | None = None
    nhl_id: str | None = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthUserOut(BaseModel):
    id: str
    email: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: AuthUserOut
```

- [ ] **Step 2: Run the test suite to confirm no regressions**

```bash
cd apps/api && pytest tests/ -x -q
```

Expected: All existing tests pass.

- [ ] **Step 3: Commit**

```bash
cd apps/api && git add models/schemas.py
git commit -m "feat(auth): add auth and player Pydantic schemas"
```

---

### Task 2: Add get_player_repository to dependencies.py

**Files:**
- Modify: `apps/api/core/dependencies.py`

- [ ] **Step 1: Add import and factory function**

In `apps/api/core/dependencies.py`, after the existing `get_league_profile_repository` function, add:

```python
def get_player_repository() -> PlayerRepository:
    from repositories.players import PlayerRepository
    return PlayerRepository(get_db())
```

- [ ] **Step 2: Run tests to confirm no regressions**

```bash
cd apps/api && pytest tests/ -x -q
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/core/dependencies.py
git commit -m "feat(players): add get_player_repository dependency"
```

---

### Task 3: Write failing tests for the Players router

**Files:**
- Create: `apps/api/tests/routers/test_players.py`

- [ ] **Step 1: Write the test file**

```python
# apps/api/tests/routers/test_players.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_player_repository
from main import app

PLAYER_1 = {"id": "p1", "name": "Connor McDavid", "team": "EDM", "position": "C", "nhl_id": "8478402"}
PLAYER_2 = {"id": "p2", "name": "Leon Draisaitl", "team": "EDM", "position": "C", "nhl_id": "8477934"}


@pytest.fixture
def mock_player_repo() -> MagicMock:
    repo = MagicMock()
    repo.list.return_value = [PLAYER_1, PLAYER_2]
    repo.get.return_value = PLAYER_1
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_player_repo: MagicMock) -> None:
    app.dependency_overrides[get_player_repository] = lambda: mock_player_repo
    yield
    app.dependency_overrides.clear()


class TestListPlayers:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/players").status_code == 200

    def test_returns_list(self, client: TestClient) -> None:
        data = client.get("/players").json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_player_has_required_fields(self, client: TestClient) -> None:
        player = client.get("/players").json()[0]
        assert "id" in player
        assert "name" in player

    def test_calls_repo_list(self, client: TestClient, mock_player_repo: MagicMock) -> None:
        client.get("/players")
        mock_player_repo.list.assert_called_once()


class TestGetPlayer:
    def test_returns_200_for_known_player(self, client: TestClient) -> None:
        assert client.get("/players/p1").status_code == 200

    def test_returns_player_data(self, client: TestClient) -> None:
        data = client.get("/players/p1").json()
        assert data["id"] == "p1"
        assert data["name"] == "Connor McDavid"

    def test_returns_404_when_not_found(
        self, client: TestClient, mock_player_repo: MagicMock
    ) -> None:
        mock_player_repo.get.return_value = None
        assert client.get("/players/nonexistent").status_code == 404

    def test_calls_repo_get_with_id(
        self, client: TestClient, mock_player_repo: MagicMock
    ) -> None:
        client.get("/players/p1")
        mock_player_repo.get.assert_called_once_with("p1")
```

- [ ] **Step 2: Run tests — expect ImportError or 404 (router doesn't exist yet)**

```bash
cd apps/api && pytest tests/routers/test_players.py -v
```

Expected: FAIL (router not registered → 404 on all route calls, or ImportError)

---

### Task 4: Implement the Players router

**Files:**
- Create: `apps/api/routers/players.py`

- [ ] **Step 1: Write the router**

```python
# apps/api/routers/players.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_player_repository
from models.schemas import PlayerOut
from repositories.players import PlayerRepository

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
async def list_players(
    repo: PlayerRepository = Depends(get_player_repository),
) -> list[PlayerOut]:
    """Return all NHL players in the database."""
    rows = repo.list()
    return [PlayerOut(**row) for row in rows]


@router.get("/{player_id}", response_model=PlayerOut)
async def get_player(
    player_id: str,
    repo: PlayerRepository = Depends(get_player_repository),
) -> PlayerOut:
    """Return a single player by UUID."""
    row = repo.get(player_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerOut(**row)
```

- [ ] **Step 2: Register in main.py**

In `apps/api/main.py`, add to imports:
```python
from routers import auth, players
```
And add to the router include block:
```python
app.include_router(players.router)
```
(Leave `auth` import for Task 7 — adding it here now will cause an ImportError since auth.py doesn't exist yet. Add the import in the same commit as auth.py.)

Actually, just add `players` for now:
```python
# In main.py, add to existing imports:
from routers import players  # add to the existing import block

# Add to includes:
app.include_router(players.router)
```

- [ ] **Step 3: Run players tests — expect all to pass**

```bash
cd apps/api && pytest tests/routers/test_players.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 4: Run full test suite**

```bash
cd apps/api && pytest tests/ -q
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/routers/players.py apps/api/main.py
git commit -m "feat(players): add GET /players and GET /players/{id} endpoints"
```

---

## Chunk 2: Auth Router

### Task 5: Write failing tests for the Auth router

**Files:**
- Create: `apps/api/tests/routers/test_auth.py`

- [ ] **Step 1: Write the test file**

```python
# apps/api/tests/routers/test_auth.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

# Helpers —————————————————————————————————————————————
def _make_session(access: str = "tok_access", refresh: str = "tok_refresh") -> MagicMock:
    session = MagicMock()
    session.access_token = access
    session.refresh_token = refresh
    return session


def _make_user(uid: str = "u1", email: str = "user@test.com") -> MagicMock:
    user = MagicMock()
    user.id = uid
    user.email = email
    return user


def _make_auth_response(access: str = "tok_access", refresh: str = "tok_refresh") -> MagicMock:
    resp = MagicMock()
    resp.session = _make_session(access, refresh)
    resp.user = _make_user()
    return resp


# Register ————————————————————————————————————————————
class TestRegister:
    def test_returns_200(self, client: TestClient) -> None:
        with patch("routers.auth._get_auth_client") as mock_auth:
            mock_auth.return_value.sign_up.return_value = _make_auth_response()
            resp = client.post("/auth/register", json={"email": "a@b.com", "password": "pass123"})
        assert resp.status_code == 200

    def test_returns_tokens_and_user(self, client: TestClient) -> None:
        with patch("routers.auth._get_auth_client") as mock_auth:
            mock_auth.return_value.sign_up.return_value = _make_auth_response()
            data = client.post(
                "/auth/register", json={"email": "a@b.com", "password": "pass123"}
            ).json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "user@test.com"

    def test_duplicate_email_returns_400(self, client: TestClient) -> None:
        with patch("routers.auth._get_auth_client") as mock_auth:
            mock_auth.return_value.sign_up.side_effect = Exception("User already registered")
            resp = client.post(
                "/auth/register", json={"email": "a@b.com", "password": "pass123"}
            )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]


# Login ————————————————————————————————————————————————
class TestLogin:
    def test_returns_200(self, client: TestClient) -> None:
        with patch("routers.auth._get_auth_client") as mock_auth:
            mock_auth.return_value.sign_in_with_password.return_value = _make_auth_response()
            resp = client.post("/auth/login", json={"email": "a@b.com", "password": "pass123"})
        assert resp.status_code == 200

    def test_wrong_password_returns_401(self, client: TestClient) -> None:
        with patch("routers.auth._get_auth_client") as mock_auth:
            mock_auth.return_value.sign_in_with_password.side_effect = Exception(
                "Invalid login credentials"
            )
            resp = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
        assert resp.status_code == 401


# Logout ————————————————————————————————————————————————
class TestLogout:
    def test_returns_204(self, client: TestClient) -> None:
        with patch("routers.auth._get_auth_client") as mock_auth:
            mock_auth.return_value.sign_out.return_value = None
            resp = client.post(
                "/auth/logout", headers={"Authorization": "Bearer some_token"}
            )
        assert resp.status_code == 204

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        resp = client.post("/auth/logout")
        assert resp.status_code == 401


# Refresh ——————————————————————————————————————————————
class TestRefresh:
    def test_returns_new_tokens(self, client: TestClient) -> None:
        new_session = _make_session("new_access", "new_refresh")
        with patch("routers.auth._get_auth_client") as mock_auth:
            refresh_resp = MagicMock()
            refresh_resp.session = new_session
            mock_auth.return_value.refresh_session.return_value = refresh_resp
            data = client.post(
                "/auth/refresh", json={"refresh_token": "old_refresh"}
            ).json()
        assert data["access_token"] == "new_access"
        assert data["refresh_token"] == "new_refresh"

    def test_invalid_refresh_token_returns_401(self, client: TestClient) -> None:
        with patch("routers.auth._get_auth_client") as mock_auth:
            mock_auth.return_value.refresh_session.side_effect = Exception("Invalid token")
            resp = client.post("/auth/refresh", json={"refresh_token": "bad"})
        assert resp.status_code == 401


# Me ———————————————————————————————————————————————————
class TestMe:
    def test_returns_user_info(self, client: TestClient) -> None:
        with patch("core.dependencies.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_user = _make_user()
            mock_db.auth.get_user.return_value = MagicMock(user=mock_user)
            mock_get_db.return_value = mock_db
            data = client.get(
                "/auth/me", headers={"Authorization": "Bearer valid_token"}
            ).json()
        assert data["id"] == "u1"
        assert data["email"] == "user@test.com"

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        resp = client.get("/auth/me")
        assert resp.status_code == 401
```

- [ ] **Step 2: Run tests — expect failure (router not found)**

```bash
cd apps/api && pytest tests/routers/test_auth.py -v
```

Expected: FAIL (404 / ImportError — auth router not registered)

---

### Task 6: Implement the Auth router

**Files:**
- Create: `apps/api/routers/auth.py`

- [ ] **Step 1: Write the router**

```python
# apps/api/routers/auth.py
"""
Auth router — thin wrapper around Supabase Auth.

Supabase owns all credential storage and JWT signing.
This router centralises error handling and response shape for:
  - Chrome extension token exchange (Phase 4)
  - Server-side Next.js token refresh
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user, get_db
from models.schemas import AuthResponse, AuthUserOut, LoginRequest, RefreshRequest, RegisterRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_client() -> Any:
    """Return the Supabase auth client (extracted for testability)."""
    return get_db().auth


def _build_auth_response(resp: Any) -> AuthResponse:
    """Convert a supabase-py auth response to AuthResponse schema."""
    return AuthResponse(
        access_token=resp.session.access_token,
        refresh_token=resp.session.refresh_token,
        user=AuthUserOut(id=resp.user.id, email=resp.user.email),
    )


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest) -> AuthResponse:
    """Create a new user account via Supabase Auth."""
    try:
        resp = _get_auth_client().sign_up({"email": req.email, "password": req.password})
        return _build_auth_response(resp)
    except Exception as exc:
        msg = str(exc).lower()
        if "already registered" in msg or "already exists" in msg:
            raise HTTPException(status_code=400, detail="Email already registered") from exc
        logger.warning("Register failed: %s", exc)
        raise HTTPException(status_code=400, detail="Registration failed") from exc


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest) -> AuthResponse:
    """Sign in with email + password."""
    try:
        resp = _get_auth_client().sign_in_with_password(
            {"email": req.email, "password": req.password}
        )
        return _build_auth_response(resp)
    except Exception as exc:
        logger.warning("Login failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc


@router.post("/logout", status_code=204)
async def logout(user: dict[str, Any] = Depends(get_current_user)) -> None:
    """Sign out the current user session."""
    try:
        _get_auth_client().sign_out()
    except Exception as exc:
        logger.warning("Logout failed: %s", exc)
        # Sign-out failure is non-fatal — token will expire naturally


@router.post("/refresh")
async def refresh(req: RefreshRequest) -> dict[str, str]:
    """Exchange a refresh token for a new access token."""
    try:
        resp = _get_auth_client().refresh_session(req.refresh_token)
        return {
            "access_token": resp.session.access_token,
            "refresh_token": resp.session.refresh_token,
        }
    except Exception as exc:
        logger.warning("Token refresh failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from exc


@router.get("/me", response_model=AuthUserOut)
async def me(user: dict[str, Any] = Depends(get_current_user)) -> AuthUserOut:
    """Return the authenticated user's id and email."""
    return AuthUserOut(id=user["id"], email=user["email"])
```

- [ ] **Step 2: Register auth router in main.py**

Add `auth` to the existing import in `apps/api/main.py`:

```python
from routers import (
    auth,
    exports,
    health,
    league_profiles,
    players,
    rankings,
    scoring_configs,
    sources,
    stripe,
    user_kits,
)
```

And add to the include block:
```python
app.include_router(auth.router)
```

- [ ] **Step 3: Run auth tests — expect all to pass**

```bash
cd apps/api && pytest tests/routers/test_auth.py -v
```

Expected: All tests pass.

- [ ] **Step 4: Run full suite**

```bash
cd apps/api && pytest tests/ -q
```

Expected: All tests pass.

- [ ] **Step 5: Lint**

```bash
cd apps/api && ruff check . && ruff format --check .
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add apps/api/routers/auth.py apps/api/main.py
git commit -m "feat(auth): add POST /auth/register,login,logout,refresh and GET /auth/me"
```

---

## Chunk 3: Final Verification

### Task 7: Update Notion task statuses

- [ ] **Step 1: Mark "Build auth router" as Done in Notion**

  Update task `32548885-3275-81ec-9228-ec5116e7cf05` status to "Done".

- [ ] **Step 2: Mark "Add user_kits, exports, subscriptions tables" as Done in Notion**

  Update task `32048885-3275-81d1-ba69-d68c2924305d` status to "Done" (migrations were in 001_initial_schema.sql — already applied).

- [ ] **Step 3: Update apps/api/CLAUDE.md Phase 2 status table**

  Mark `routers/auth.py` and `routers/players.py` as ✅ Complete.

- [ ] **Step 4: Final test run**

```bash
cd apps/api && pytest tests/ -q --tb=short
```

Expected: All tests pass with coverage output.

- [ ] **Step 5: Final commit**

```bash
git add apps/api/CLAUDE.md
git commit -m "docs(api): mark auth router and players router as complete in phase 2 status"
```
