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
SOURCE_WEIGHTS = {"hashtag": 1.0, "dailyfaceoff": 0.5}
SCORING_CONFIG_ID = "sc-abc"
PLATFORM = "espn"
LEAGUE_PROFILE_ID = "lp-xyz"
RANKINGS = [{"composite_rank": 1, "player_id": "p1", "projected_fantasy_points": 290.0}]

# Convenience tuples for the 5-param and 6-param signatures
CACHE_GET_ARGS = (SEASON, SOURCE_WEIGHTS, SCORING_CONFIG_ID, PLATFORM, LEAGUE_PROFILE_ID)
CACHE_SET_ARGS = (*CACHE_GET_ARGS, RANKINGS)


# ---------------------------------------------------------------------------
# _make_rankings_key (pure function — no mock needed)
# ---------------------------------------------------------------------------


class TestMakeRankingsKey:
    def test_includes_season(self) -> None:
        key = _make_rankings_key(SEASON, {"a": 1}, "sc-1", "espn", None)
        assert SEASON in key

    def test_deterministic_regardless_of_weight_dict_order(self) -> None:
        k1 = _make_rankings_key(SEASON, {"a": 1, "b": 2}, "sc-1", "espn", None)
        k2 = _make_rankings_key(SEASON, {"b": 2, "a": 1}, "sc-1", "espn", None)
        assert k1 == k2

    def test_different_weights_produce_different_keys(self) -> None:
        k1 = _make_rankings_key(SEASON, {"a": 1}, "sc-1", "espn", None)
        k2 = _make_rankings_key(SEASON, {"a": 2}, "sc-1", "espn", None)
        assert k1 != k2

    def test_different_seasons_produce_different_keys(self) -> None:
        k1 = _make_rankings_key("2024-25", SOURCE_WEIGHTS, "sc-1", "espn", None)
        k2 = _make_rankings_key("2025-26", SOURCE_WEIGHTS, "sc-1", "espn", None)
        assert k1 != k2

    def test_different_scoring_configs_produce_different_keys(self) -> None:
        k1 = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-1", "espn", None)
        k2 = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-2", "espn", None)
        assert k1 != k2

    def test_different_platforms_produce_different_keys(self) -> None:
        k1 = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-1", "espn", None)
        k2 = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-1", "yahoo", None)
        assert k1 != k2

    def test_different_league_profiles_produce_different_keys(self) -> None:
        k1 = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-1", "espn", "lp-1")
        k2 = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-1", "espn", "lp-2")
        assert k1 != k2

    def test_none_and_string_league_profile_differ(self) -> None:
        k1 = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-1", "espn", None)
        k2 = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-1", "espn", "lp-1")
        assert k1 != k2

    def test_key_format_starts_with_rankings_prefix(self) -> None:
        key = _make_rankings_key(SEASON, SOURCE_WEIGHTS, "sc-1", "espn", None)
        assert key.startswith(f"rankings:{SEASON}:")


# ---------------------------------------------------------------------------
# CacheService — no Redis configured (no-op mode)
# ---------------------------------------------------------------------------


class TestCacheServiceNoRedis:
    def test_available_is_false_when_no_url(self) -> None:
        svc = CacheService(redis_url="")
        assert svc.available is False

    def test_get_rankings_returns_none_when_no_redis(self) -> None:
        svc = CacheService(redis_url="")
        assert svc.get_rankings(*CACHE_GET_ARGS) is None

    def test_set_rankings_is_noop_when_no_redis(self) -> None:
        svc = CacheService(redis_url="")
        svc.set_rankings(*CACHE_SET_ARGS)  # must not raise

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
    """CacheService with mock Redis injected directly into _client."""
    svc = CacheService(redis_url="")
    svc._client = mock_redis
    return svc


class TestCacheServiceWithRedis:
    def test_available_is_true(self, cache_with_redis: CacheService) -> None:
        assert cache_with_redis.available is True

    def test_get_returns_none_on_cache_miss(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.get.return_value = None
        assert cache_with_redis.get_rankings(*CACHE_GET_ARGS) is None

    def test_get_returns_deserialized_data_on_hit(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.get.return_value = json.dumps(RANKINGS)
        result = cache_with_redis.get_rankings(*CACHE_GET_ARGS)
        assert result == RANKINGS

    def test_set_calls_setex_with_correct_ttl(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        cache_with_redis.set_rankings(*CACHE_SET_ARGS)
        mock_redis.setex.assert_called_once()
        _, ttl, _ = mock_redis.setex.call_args.args
        assert ttl == 6 * 60 * 60  # 6 hours

    def test_set_serializes_data_as_json(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        cache_with_redis.set_rankings(*CACHE_SET_ARGS)
        _, _, payload = mock_redis.setex.call_args.args
        assert json.loads(payload) == RANKINGS

    def test_get_uses_correct_key(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.get.return_value = None
        cache_with_redis.get_rankings(*CACHE_GET_ARGS)
        expected_key = _make_rankings_key(*CACHE_GET_ARGS)
        mock_redis.get.assert_called_once_with(expected_key)

    def test_set_uses_same_key_as_get(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        cache_with_redis.set_rankings(*CACHE_SET_ARGS)
        key_used, _, _ = mock_redis.setex.call_args.args
        assert key_used == _make_rankings_key(*CACHE_GET_ARGS)

    def test_get_returns_none_on_redis_error(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.get.side_effect = Exception("connection refused")
        assert cache_with_redis.get_rankings(*CACHE_GET_ARGS) is None

    def test_set_does_not_raise_on_redis_error(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.setex.side_effect = Exception("connection refused")
        cache_with_redis.set_rankings(*CACHE_SET_ARGS)  # must not raise

    def test_invalidate_uses_scan_not_keys(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.scan.return_value = (0, [])
        cache_with_redis.invalidate_rankings(SEASON)
        mock_redis.scan.assert_called()
        mock_redis.keys.assert_not_called()

    def test_invalidate_deletes_matched_keys(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.scan.return_value = (0, ["rankings:2025-26:abc123"])
        cache_with_redis.invalidate_rankings(SEASON)
        mock_redis.delete.assert_called_once_with("rankings:2025-26:abc123")

    def test_invalidate_skips_delete_when_no_keys(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        mock_redis.scan.return_value = (0, [])
        cache_with_redis.invalidate_rankings(SEASON)
        mock_redis.delete.assert_not_called()

    def test_invalidate_paginates_with_scan(
        self, cache_with_redis: CacheService, mock_redis: MagicMock
    ) -> None:
        # First call returns cursor=42 with 1 key; second returns cursor=0
        mock_redis.scan.side_effect = [
            (42, ["rankings:2025-26:key1"]),
            (0, ["rankings:2025-26:key2"]),
        ]
        cache_with_redis.invalidate_rankings(SEASON)
        assert mock_redis.scan.call_count == 2
        mock_redis.delete.assert_called_once_with(
            "rankings:2025-26:key1", "rankings:2025-26:key2"
        )
