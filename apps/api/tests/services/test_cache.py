"""
Unit tests for services/cache.py.

Redis is never hit — we mock the redis client at construction time using
unittest.mock.patch so CacheService behaves as if Redis is available.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from services.cache import CacheService, _make_rankings_key

SEASON = "2025-26"
WEIGHTS = {"nhl_com": 50.0, "moneypuck": 50.0}
RANKINGS = [{"composite_rank": 1, "player_id": "p1", "composite_score": 0.9}]


# ---------------------------------------------------------------------------
# _make_rankings_key (pure function — no mock needed)
# ---------------------------------------------------------------------------


class TestMakeRankingsKey:
    def test_includes_season(self) -> None:
        key = _make_rankings_key("2025-26", {"a": 1})
        assert "2025-26" in key

    def test_deterministic_regardless_of_dict_order(self) -> None:
        k1 = _make_rankings_key(SEASON, {"a": 1, "b": 2})
        k2 = _make_rankings_key(SEASON, {"b": 2, "a": 1})
        assert k1 == k2

    def test_different_weights_produce_different_keys(self) -> None:
        k1 = _make_rankings_key(SEASON, {"a": 1})
        k2 = _make_rankings_key(SEASON, {"a": 2})
        assert k1 != k2

    def test_different_seasons_produce_different_keys(self) -> None:
        k1 = _make_rankings_key("2024-25", WEIGHTS)
        k2 = _make_rankings_key("2025-26", WEIGHTS)
        assert k1 != k2


# ---------------------------------------------------------------------------
# CacheService — no Redis configured (no-op mode)
# ---------------------------------------------------------------------------


class TestCacheServiceNoRedis:
    def test_available_is_false_when_no_url(self) -> None:
        svc = CacheService(redis_url="")
        assert svc.available is False

    def test_get_rankings_returns_none_when_no_redis(self) -> None:
        svc = CacheService(redis_url="")
        assert svc.get_rankings(SEASON, WEIGHTS) is None

    def test_set_rankings_is_noop_when_no_redis(self) -> None:
        svc = CacheService(redis_url="")
        svc.set_rankings(SEASON, WEIGHTS, RANKINGS)  # must not raise

    def test_invalidate_rankings_is_noop_when_no_redis(self) -> None:
        svc = CacheService(redis_url="")
        svc.invalidate_rankings(SEASON)  # must not raise


# ---------------------------------------------------------------------------
# CacheService — with mocked Redis client
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> MagicMock:
    return MagicMock()


@pytest.fixture
def cache_with_redis(mock_redis: MagicMock) -> CacheService:
    """CacheService with mock Redis injected directly into _client.

    redis is imported lazily inside CacheService.__init__, so we can't patch
    the module attribute. Instead we construct with no URL (no-op mode) and
    then manually set _client to the mock.
    """
    svc = CacheService(redis_url="")
    svc._client = mock_redis  # bypass lazy import entirely
    return svc


class TestCacheServiceWithRedis:
    def test_available_is_true(self, cache_with_redis: CacheService) -> None:
        assert cache_with_redis.available is True

    def test_get_returns_none_on_cache_miss(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.get.return_value = None
        assert cache_with_redis.get_rankings(SEASON, WEIGHTS) is None

    def test_get_returns_deserialized_data_on_hit(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.get.return_value = json.dumps(RANKINGS)
        result = cache_with_redis.get_rankings(SEASON, WEIGHTS)
        assert result == RANKINGS

    def test_set_calls_setex_with_correct_ttl(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        cache_with_redis.set_rankings(SEASON, WEIGHTS, RANKINGS)
        mock_redis.setex.assert_called_once()
        _, ttl, _ = mock_redis.setex.call_args.args
        assert ttl == 6 * 60 * 60  # 6 hours

    def test_set_serializes_data_as_json(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        cache_with_redis.set_rankings(SEASON, WEIGHTS, RANKINGS)
        _, _, payload = mock_redis.setex.call_args.args
        assert json.loads(payload) == RANKINGS

    def test_get_uses_correct_key(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.get.return_value = None
        cache_with_redis.get_rankings(SEASON, WEIGHTS)
        expected_key = _make_rankings_key(SEASON, WEIGHTS)
        mock_redis.get.assert_called_once_with(expected_key)

    def test_set_uses_same_key_as_get(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        cache_with_redis.set_rankings(SEASON, WEIGHTS, RANKINGS)
        key_used, _, _ = mock_redis.setex.call_args.args
        assert key_used == _make_rankings_key(SEASON, WEIGHTS)

    def test_get_returns_none_on_redis_error(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.get.side_effect = Exception("connection refused")
        # Must not raise — degrades gracefully
        assert cache_with_redis.get_rankings(SEASON, WEIGHTS) is None

    def test_set_does_not_raise_on_redis_error(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.setex.side_effect = Exception("connection refused")
        cache_with_redis.set_rankings(SEASON, WEIGHTS, RANKINGS)  # must not raise

    def test_invalidate_calls_keys_then_delete(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.keys.return_value = ["rankings:2025-26:abc123"]
        cache_with_redis.invalidate_rankings(SEASON)
        mock_redis.keys.assert_called_once_with(f"rankings:{SEASON}:*")
        mock_redis.delete.assert_called_once_with("rankings:2025-26:abc123")

    def test_invalidate_skips_delete_when_no_keys(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.keys.return_value = []
        cache_with_redis.invalidate_rankings(SEASON)
        mock_redis.delete.assert_not_called()
