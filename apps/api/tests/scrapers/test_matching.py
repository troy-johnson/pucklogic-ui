# apps/api/tests/scrapers/test_matching.py
"""Unit tests for scrapers/matching.py — no DB, no HTTP."""
from __future__ import annotations

import pytest

from scrapers.matching import PlayerMatcher

PLAYERS = [
    {"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"},
    {"id": "p2", "name": "Leon Draisaitl", "nhl_id": "8477934"},
    {"id": "p3", "name": "Jesperi Kotkaniemi", "nhl_id": "8481522"},
    {"id": "p4", "name": "Nathan MacKinnon", "nhl_id": "8477492"},
]

ALIASES = [
    {"alias_name": "J. Kotkaniemi", "player_id": "p3", "source": "hashtag"},
    {"alias_name": "Mac Kinnon", "player_id": "p4", "source": "test"},
]


@pytest.fixture
def matcher() -> PlayerMatcher:
    return PlayerMatcher(players=PLAYERS, aliases=ALIASES)


class TestExactMatch:
    def test_exact_name_match(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("Connor McDavid") == "p1"

    def test_case_insensitive(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("connor mcdavid") == "p1"

    def test_strips_whitespace(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("  Leon Draisaitl  ") == "p2"


class TestAliasMatch:
    def test_finds_via_alias(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("J. Kotkaniemi") == "p3"

    def test_alias_case_insensitive(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("j. kotkaniemi") == "p3"

    def test_ambiguous_alias_same_name_different_players_returns_none(self) -> None:
        # Two players mapped to the same alias (from different sources) — the
        # alias lookup is ambiguous so it falls through to fuzzy. The canonical
        # names are dissimilar enough that fuzzy also fails → None.
        players = [
            {"id": "x1", "name": "Firstname Zzzquux", "nhl_id": "1"},
            {"id": "x2", "name": "Otherguy Zyxwvut", "nhl_id": "2"},
        ]
        aliases = [
            {"alias_name": "Ambiguous Shared", "player_id": "x1", "source": "src_a"},
            {"alias_name": "Ambiguous Shared", "player_id": "x2", "source": "src_b"},
        ]
        m = PlayerMatcher(players=players, aliases=aliases)
        assert m.resolve("Ambiguous Shared") is None


class TestFuzzyMatch:
    def test_fuzzy_matches_close_name(self, matcher: PlayerMatcher) -> None:
        # "McDavid Connor" — transposed — should still match
        result = matcher.resolve("McDavid Connor")
        assert result == "p1"

    def test_returns_none_below_threshold(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("Totally Unknown Player") is None

    def test_custom_threshold_strict(self, matcher: PlayerMatcher) -> None:
        # Very strict threshold — garbage should not match at 99
        result = matcher.resolve("zzzzz yyyyy", threshold=99)
        assert result is None


class TestEdgeCases:
    def test_empty_name_returns_none(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("") is None

    def test_empty_players_list(self) -> None:
        m = PlayerMatcher(players=[], aliases=[])
        assert m.resolve("Connor McDavid") is None
