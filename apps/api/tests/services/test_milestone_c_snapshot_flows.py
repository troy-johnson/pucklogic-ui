"""Direct Milestone C close-snapshot flow tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from services.draft_sessions import DraftSessionService


def _build_service() -> tuple[
    DraftSessionService, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock
]:
    draft_repo = MagicMock()
    sub_repo = MagicMock()
    projection_repo = MagicMock()
    league_repo = MagicMock()
    scoring_repo = MagicMock()

    service = DraftSessionService(
        draft_session_repo=draft_repo,
        subscription_repo=sub_repo,
        projection_repo=projection_repo,
        league_profile_repo=league_repo,
        scoring_config_repo=scoring_repo,
        inactivity_timeout=timedelta(hours=2),
    )
    return service, draft_repo, projection_repo, scoring_repo, league_repo, sub_repo


def test_clean_close_snapshot_written_but_expired_missing_recipe_skips() -> None:
    now = datetime.now(UTC)
    service, draft_repo, projection_repo, scoring_repo, _league_repo, _sub_repo = _build_service()

    scoring_repo.get.return_value = {"stat_weights": {"g": 1.0}}
    projection_repo.get_by_season.return_value = [
        {
            "g": 10,
            "season": "2026-27",
            "player_id": "p1",
            "sources": {
                "name": "hashtag",
                "default_weight": 1.0,
                "is_paid": False,
                "user_id": None,
            },
            "players": {"name": "Player One", "team": "TOR", "position": "C"},
            "player_platform_positions": [{"platform": "espn", "positions": ["C"]}],
            "schedule_scores": [{"season": "2026-27", "schedule_score": 0.0, "off_night_games": 0}],
        }
    ]

    # Clean-close session with full recipe => write snapshot
    draft_repo.get_session_by_id.return_value = {
        "session_id": "ses_clean",
        "user_id": "usr_1",
        "status": "ended",
        "season": "2026-27",
        "league_profile_id": None,
        "scoring_config_id": "sc_1",
        "source_weights": {"hashtag": 1.0},
        "platform": "espn",
    }
    service.snapshot_rankings_at_close(session_id="ses_clean", user_id="usr_1", now=now)
    assert draft_repo.snapshot_rankings_at_close.call_count == 1

    # Expired/abandoned-style row with missing recipe => no snapshot write
    draft_repo.get_session_by_id.return_value = {
        "session_id": "ses_expired",
        "user_id": "usr_1",
        "status": "expired",
        "season": "2026-27",
        "scoring_config_id": None,
        "source_weights": None,
        "platform": "espn",
    }
    service.snapshot_rankings_at_close(session_id="ses_expired", user_id="usr_1", now=now)
    assert draft_repo.snapshot_rankings_at_close.call_count == 1
