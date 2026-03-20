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
from fastapi.responses import JSONResponse

from core.dependencies import get_current_user, get_db
from models.schemas import AuthResponse, AuthUserOut, LoginRequest, RefreshRequest, RegisterRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_auth_response(resp: Any) -> AuthResponse:
    """Convert a supabase-py auth response to AuthResponse schema."""
    return AuthResponse(
        access_token=resp.session.access_token,
        refresh_token=resp.session.refresh_token,
        user=AuthUserOut(id=resp.user.id, email=resp.user.email),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=200,
    responses={
        202: {
            "description": "Email confirmation required — session not yet available",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "example": {
                            "message": (
                                "Confirmation email sent. "
                                "Please verify your email to complete registration."
                            )
                        },
                    }
                }
            },
        }
    },
)
async def register(req: RegisterRequest) -> AuthResponse | dict[str, str]:
    """Create a new user account via Supabase Auth."""
    try:
        resp = get_db().auth.sign_up({"email": req.email, "password": req.password})
        if resp.session is None:
            # Email confirmation required — session not yet available
            return JSONResponse(
                status_code=202,
                content={
                    "message": (
                        "Confirmation email sent. "
                        "Please verify your email to complete registration."
                    )
                },
            )
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
        resp = get_db().auth.sign_in_with_password({"email": req.email, "password": req.password})
        return _build_auth_response(resp)
    except Exception as exc:
        logger.warning("Login failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc


@router.post("/logout", status_code=204)
async def logout(user: dict[str, Any] = Depends(get_current_user)) -> None:
    """Sign out the current user session."""
    try:
        get_db().auth.admin.sign_out(user["token"])
    except Exception as exc:
        logger.warning("Logout failed: %s", exc)
        # Sign-out failure is non-fatal — token will expire naturally


@router.post("/refresh")
async def refresh(req: RefreshRequest) -> dict[str, str]:
    """Exchange a refresh token for a new access token."""
    try:
        resp = get_db().auth.refresh_session(req.refresh_token)
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
