"""
FastAPI dependency injection helpers.

Pattern: module-level singletons for expensive objects (Supabase client,
CacheService); cheap repositories are constructed fresh per request so they
are easy to mock in tests via `app.dependency_overrides`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import Header, HTTPException

from core.config import settings
from repositories.rankings import RankingsRepository
from repositories.sources import SourceRepository
from services.cache import CacheService

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supabase singleton
# ---------------------------------------------------------------------------

_supabase_client: "Client | None" = None


def get_db() -> "Client":
    """Return (and lazily create) the shared Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client

        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _supabase_client


# ---------------------------------------------------------------------------
# Cache singleton
# ---------------------------------------------------------------------------

_cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    """Return (and lazily create) the shared CacheService."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService(settings.redis_url)
    return _cache_service


# ---------------------------------------------------------------------------
# Repository factories (new instance per request — cheap, easy to override)
# ---------------------------------------------------------------------------


def get_source_repository() -> SourceRepository:
    return SourceRepository(get_db())


def get_rankings_repository() -> RankingsRepository:
    return RankingsRepository(get_db())


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def get_current_user(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Extract and verify the Supabase JWT from the Authorization header.

    Returns the user dict from Supabase auth on success.
    Raises HTTP 401 on missing / invalid token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.removeprefix("Bearer ")
    try:
        response = get_db().auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": response.user.id, "email": response.user.email}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Auth failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token") from exc
