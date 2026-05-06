"""
Tests for Phase 3 Trends Pydantic schemas.
Covers: ShapValues, TrendedPlayer, TrendsResponse
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from models.schemas import (
    DraftManualPickRequest,
    DraftPick,
    DraftSession,
    DraftSessionStartRequest,
    DraftSyncState,
    ShapValues,
    TrendedPlayer,
    TrendsResponse,
)

# ---------------------------------------------------------------------------
# ShapValues
# ---------------------------------------------------------------------------


class TestShapValues:
    def test_valid_breakout_only(self) -> None:
        sv = ShapValues(breakout={"g_minus_ixg": 0.18, "pp_unit": 0.12})
        assert sv.breakout["g_minus_ixg"] == pytest.approx(0.18)
        assert sv.regression == {}

    def test_valid_regression_only(self) -> None:
        sv = ShapValues(regression={"sh_pct_delta": 0.09})
        assert sv.regression["sh_pct_delta"] == pytest.approx(0.09)
        assert sv.breakout == {}

    def test_valid_both_populated(self) -> None:
        sv = ShapValues(
            breakout={"g_minus_ixg": 0.18},
            regression={"high_pdo": 0.07},
        )
        assert sv.breakout and sv.regression

    def test_both_empty_raises(self) -> None:
        """Empty ShapValues must be rejected — caller should use shap_values=None instead."""
        with pytest.raises(ValidationError, match="at least one entry"):
            ShapValues(breakout={}, regression={})

    def test_default_empty_raises(self) -> None:
        """Default construction (no args) produces both-empty — must raise."""
        with pytest.raises(ValidationError, match="at least one entry"):
            ShapValues()


# ---------------------------------------------------------------------------
# TrendedPlayer
# ---------------------------------------------------------------------------


class TestTrendedPlayer:
    def _full(self) -> dict:
        return {
            "player_id": "abc-123",
            "name": "Connor McDavid",
            "position": "C",
            "team": "EDM",
            "breakout_score": 0.82,
            "regression_risk": 0.05,
            "confidence": 0.91,
            "projection_tier": "HIGH",
            "projection_pts": 320.5,
            "breakout_signals": {"g_below_ixg": True, "prime_age_window": False},
            "regression_signals": {"high_pdo": False},
            "shap_top3": {"breakout": [["g_minus_ixg", 0.18], ["pp_unit", 0.12]]},
            "shap_values": {"breakout": {"g_minus_ixg": 0.18}, "regression": {}},
        }

    def test_full_construction(self) -> None:
        player = TrendedPlayer(**self._full())
        assert player.name == "Connor McDavid"
        assert player.breakout_score == pytest.approx(0.82)
        assert player.projection_tier == "HIGH"

    def test_all_optional_fields_none(self) -> None:
        player = TrendedPlayer(player_id="abc-123", name="Test Player")
        assert player.position is None
        assert player.team is None
        assert player.breakout_score is None
        assert player.regression_risk is None
        assert player.confidence is None
        assert player.projection_tier is None
        assert player.projection_pts is None
        assert player.breakout_signals is None
        assert player.regression_signals is None
        assert player.shap_top3 is None
        assert player.shap_values is None

    def test_breakout_score_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            TrendedPlayer(player_id="x", name="X", breakout_score=1.3)

    def test_breakout_score_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            TrendedPlayer(player_id="x", name="X", breakout_score=-0.1)

    def test_regression_risk_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TrendedPlayer(player_id="x", name="X", regression_risk=1.001)

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TrendedPlayer(player_id="x", name="X", confidence=-0.01)

    def test_scores_at_boundary_valid(self) -> None:
        player = TrendedPlayer(
            player_id="x",
            name="X",
            breakout_score=0.0,
            regression_risk=1.0,
            confidence=1.0,
        )
        assert player.breakout_score == pytest.approx(0.0)

    def test_invalid_projection_tier_raises(self) -> None:
        with pytest.raises(ValidationError):
            TrendedPlayer(player_id="x", name="X", projection_tier="VERY_HIGH")

    def test_lowercase_projection_tier_raises(self) -> None:
        with pytest.raises(ValidationError):
            TrendedPlayer(player_id="x", name="X", projection_tier="high")

    def test_invalid_position_raises(self) -> None:
        with pytest.raises(ValidationError):
            TrendedPlayer(player_id="x", name="X", position="UTIL")

    def test_strict_bool_rejects_integer(self) -> None:
        """breakout_signals must use actual booleans — int 1/0 must be rejected."""
        with pytest.raises(ValidationError):
            TrendedPlayer(
                player_id="x",
                name="X",
                breakout_signals={"g_below_ixg": 1},  # int, not bool
            )

    def test_strict_bool_accepts_bool(self) -> None:
        player = TrendedPlayer(
            player_id="x",
            name="X",
            breakout_signals={"g_below_ixg": True, "prime_age_window": False},
        )
        assert player.breakout_signals == {"g_below_ixg": True, "prime_age_window": False}

    def test_shap_values_none_is_valid(self) -> None:
        player = TrendedPlayer(player_id="x", name="X", shap_values=None)
        assert player.shap_values is None

    def test_shap_values_populated(self) -> None:
        player = TrendedPlayer(
            player_id="x",
            name="X",
            shap_values={"breakout": {"g_minus_ixg": 0.18}, "regression": {}},
        )
        assert player.shap_values is not None
        assert player.shap_values.breakout["g_minus_ixg"] == pytest.approx(0.18)


# ---------------------------------------------------------------------------
# TrendsResponse
# ---------------------------------------------------------------------------


class TestTrendsResponse:
    def _make_player(self, pid: str = "abc") -> TrendedPlayer:
        return TrendedPlayer(player_id=pid, name=f"Player {pid}")

    def test_player_count_computed_from_list(self) -> None:
        players = [self._make_player("a"), self._make_player("b"), self._make_player("c")]
        resp = TrendsResponse(
            season="2025-26",
            has_trends=True,
            updated_at=datetime.now(UTC),
            players=players,
        )
        assert resp.player_count == 3

    def test_empty_players_count_zero(self) -> None:
        resp = TrendsResponse(season="2025-26", has_trends=False, players=[])
        assert resp.player_count == 0

    def test_updated_at_none_allowed(self) -> None:
        """updated_at=None signals no trends computed yet; has_trends=False."""
        resp = TrendsResponse(season="2025-26", has_trends=False, updated_at=None, players=[])
        assert resp.updated_at is None
        assert not resp.has_trends

    def test_updated_at_populated(self) -> None:
        now = datetime.now(UTC)
        resp = TrendsResponse(
            season="2025-26",
            has_trends=True,
            updated_at=now,
            players=[self._make_player()],
        )
        assert resp.updated_at == now

    def test_has_trends_true_without_updated_at_raises(self) -> None:
        """has_trends=True requires updated_at.

        The ML pipeline must record when scores were written.
        """
        with pytest.raises(ValidationError, match="updated_at must be set"):
            TrendsResponse(
                season="2025-26",
                has_trends=True,
                updated_at=None,
                players=[self._make_player()],
            )

    def test_season_preserved(self) -> None:
        resp = TrendsResponse(season="2024-25", has_trends=False, players=[])
        assert resp.season == "2024-25"

    def test_full_serialization(self) -> None:
        """Round-trip through model_dump to catch any serialization issues."""
        player = TrendedPlayer(
            player_id="abc-123",
            name="Connor McDavid",
            position="C",
            breakout_score=0.82,
            projection_tier="HIGH",
            breakout_signals={"g_below_ixg": True},
            shap_values={"breakout": {"g_minus_ixg": 0.18}, "regression": {}},
        )
        resp = TrendsResponse(
            season="2025-26",
            has_trends=True,
            updated_at=datetime(2026, 8, 1),
            players=[player],
        )
        data = resp.model_dump()
        assert data["player_count"] == 1
        assert data["players"][0]["breakout_score"] == pytest.approx(0.82)
        assert data["players"][0]["projection_tier"] == "HIGH"


# ---------------------------------------------------------------------------
# Live Draft Session schemas — Phase 8b Wave 1
# ---------------------------------------------------------------------------


class TestDraftPick:
    def test_accepts_auto_pick_with_player_id(self) -> None:
        pick = DraftPick(
            pick_number=1,
            platform="espn",
            ingestion_mode="auto",
            timestamp=datetime.now(UTC),
            player_id="8478402",
        )
        assert pick.player_id == "8478402"

    def test_requires_player_id_or_lookup_payload(self) -> None:
        with pytest.raises(ValidationError, match="player_id or player_lookup"):
            DraftPick(
                pick_number=1,
                platform="espn",
                ingestion_mode="auto",
                timestamp=datetime.now(UTC),
            )

    def test_rejects_unknown_ingestion_mode(self) -> None:
        with pytest.raises(ValidationError):
            DraftPick(
                pick_number=1,
                platform="espn",
                ingestion_mode="keyboard",
                timestamp=datetime.now(UTC),
                player_id="8478402",
            )


class TestDraftManualPickRequest:
    def test_accepts_player_id_identifier(self) -> None:
        req = DraftManualPickRequest(pick_number=19, player_id="8478402")
        assert req.player_id == "8478402"

    def test_accepts_player_lookup_identifier(self) -> None:
        req = DraftManualPickRequest(
            pick_number=19,
            player_lookup={"espn_player_id": "401"},
        )
        assert req.player_lookup == {"espn_player_id": "401"}

    def test_requires_player_identity(self) -> None:
        with pytest.raises(ValidationError, match="player_id, player_name, or player_lookup"):
            DraftManualPickRequest(pick_number=19)


class TestDraftSession:
    def test_accepts_active_session_with_sync_state(self) -> None:
        session = DraftSession(
            session_id="ses_123",
            user_id="usr_123",
            platform="espn",
            season="2026-27",
            league_profile_id="lp_123",
            scoring_config_id="sc_123",
            source_weights={"hashtag": 1.0},
            status="active",
            sync_state=DraftSyncState(last_processed_pick=12, sync_health="healthy"),
            closing_rankings_snapshot=None,
            accepted_picks=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            last_heartbeat_at=datetime.now(UTC),
        )
        assert session.status == "active"
        assert session.sync_state.last_processed_pick == 12

    def test_rejects_unknown_platform(self) -> None:
        with pytest.raises(ValidationError):
            DraftSession(
                session_id="ses_123",
                user_id="usr_123",
                platform="sleeper",
                season="2026-27",
                league_profile_id="lp_123",
                scoring_config_id="sc_123",
                source_weights={"hashtag": 1.0},
                status="active",
                sync_state=DraftSyncState(last_processed_pick=0, sync_health="healthy"),
                closing_rankings_snapshot=None,
                accepted_picks=[],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                last_heartbeat_at=datetime.now(UTC),
            )

    def test_rejects_unknown_status(self) -> None:
        with pytest.raises(ValidationError):
            DraftSession(
                session_id="ses_123",
                user_id="usr_123",
                platform="espn",
                season="2026-27",
                league_profile_id="lp_123",
                scoring_config_id="sc_123",
                source_weights={"hashtag": 1.0},
                status="paused",
                sync_state=DraftSyncState(last_processed_pick=0, sync_health="healthy"),
                closing_rankings_snapshot=None,
                accepted_picks=[],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                last_heartbeat_at=datetime.now(UTC),
            )


class TestDraftSessionStartRequest:
    def test_requires_snapshot_recipe_fields(self) -> None:
        req = DraftSessionStartRequest(
            platform="espn",
            season="2026-27",
            league_profile_id="lp_123",
            scoring_config_id="sc_123",
            source_weights={"hashtag": 1.0},
        )
        assert req.platform == "espn"
        assert req.season == "2026-27"
        assert req.league_profile_id == "lp_123"
        assert req.scoring_config_id == "sc_123"
        assert req.source_weights == {"hashtag": 1.0}

    def test_league_profile_id_optional(self) -> None:
        req = DraftSessionStartRequest(
            platform="espn",
            season="2026-27",
            league_profile_id=None,
            scoring_config_id="sc_123",
            source_weights={"hashtag": 1.0},
        )
        assert req.league_profile_id is None

    def test_rejects_negative_source_weights(self) -> None:
        with pytest.raises(ValidationError, match="negative weights"):
            DraftSessionStartRequest(
                platform="espn",
                season="2026-27",
                league_profile_id="lp_123",
                scoring_config_id="sc_123",
                source_weights={"hashtag": -0.1, "dobber": 1.1},
            )
