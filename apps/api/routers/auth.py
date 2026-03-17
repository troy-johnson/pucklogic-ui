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

from fastapi import APIRouter, Depends, Header, HTTPException

from core.dependencies import get_current_user, get_db
from models.schemas import AuthResponse, AuthUserOut, LoginRequest, RefreshRequest, RegisterRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_client() -> Any:
    """Return the Supabase auth client (extracted for testability)."""
    return get_db().auth


async def _require_auth(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Verify Bearer token using the patchable _get_auth_client (used by logout)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ")
    try:
        response = _get_auth_client().get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": response.user.id, "email": response.user.email}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Auth failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token") from exc


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
async def logout(user: dict[str, Any] = Depends(_require_auth)) -> None:
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
