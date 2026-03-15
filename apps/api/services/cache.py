"""
Redis cache service (Upstash-compatible).

Uses the standard redis-py client pointed at an Upstash Redis TLS endpoint.
If Redis is not configured (empty REDIS_URL), all cache operations are no-ops
so local development works without a Redis instance.

Cache key format:
  rankings:{season}:{sha256(source_weights+scoring_config_id+platform+league_profile_id)}

Invalidation uses SCAN (not KEYS) so it's safe on large keyspaces.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

RANKINGS_TTL_SECONDS = 6 * 60 * 60  # 6 hours


def _make_rankings_key(
    season: str,
    source_weights: dict[str, float],
    scoring_config_id: str,
    platform: str,
    league_profile_id: str | None,
) -> str:
    """Deterministic SHA-256 cache key for a given rankings request."""
    payload = {
        "source_weights": dict(sorted(source_weights.items())),
        "scoring_config_id": scoring_config_id,
        "platform": platform,
        "league_profile_id": league_profile_id,
    }
    canonical = json.dumps(payload, sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"rankings:{season}:{digest}"


class CacheService:
    def __init__(self, redis_url: str = "") -> None:
        self._client = None
        if redis_url:
            try:
                import redis

                self._client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
            except Exception:
                logger.warning("Redis unavailable — caching disabled.")

    @property
    def available(self) -> bool:
        return self._client is not None

    def get_rankings(
        self,
        season: str,
        source_weights: dict[str, float],
        scoring_config_id: str,
        platform: str,
        league_profile_id: str | None,
    ) -> list[dict[str, Any]] | None:
        if not self._client:
            return None
        try:
            key = _make_rankings_key(
                season, source_weights, scoring_config_id, platform, league_profile_id
            )
            raw = self._client.get(key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Cache GET failed: %s", exc)
        return None

    def set_rankings(
        self,
        season: str,
        source_weights: dict[str, float],
        scoring_config_id: str,
        platform: str,
        league_profile_id: str | None,
        data: list[dict[str, Any]],
    ) -> None:
        if not self._client:
            return
        try:
            key = _make_rankings_key(
                season, source_weights, scoring_config_id, platform, league_profile_id
            )
            self._client.setex(key, RANKINGS_TTL_SECONDS, json.dumps(data))
        except Exception as exc:
            logger.warning("Cache SET failed: %s", exc)

    def invalidate_rankings(self, season: str) -> None:
        """Delete all cached rankings for a season via SCAN (safe on large keyspaces)."""
        if not self._client:
            return
        try:
            pattern = f"rankings:{season}:*"
            cursor = 0
            keys_to_delete: list[str] = []
            while True:
                cursor, keys = self._client.scan(cursor, match=pattern, count=100)
                keys_to_delete.extend(keys)
                if cursor == 0:
                    break
            if keys_to_delete:
                self._client.delete(*keys_to_delete)
        except Exception as exc:
            logger.warning("Cache invalidate failed: %s", exc)
