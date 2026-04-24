"""Authority rules for live draft sessions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from repositories.draft_sessions import DraftSessionRepository
from repositories.subscriptions import SubscriptionRepository

logger = logging.getLogger(__name__)


class TerminalSessionError(LookupError):
    """Raised when an operation targets a session that has already reached a terminal state."""


class DraftSessionService:
    def __init__(
        self,
        *,
        draft_session_repo: DraftSessionRepository,
        subscription_repo: SubscriptionRepository,
        inactivity_timeout: timedelta,
    ) -> None:
        self._draft_session_repo = draft_session_repo
        self._subscription_repo = subscription_repo
        self._inactivity_timeout = inactivity_timeout
        self._observability_counters: dict[str, int] = {
            "socket_attach": 0,
            "socket_reconnect": 0,
            "manual_fallback": 0,
            "sync_recovery": 0,
        }

    def start_session(self, *, user_id: str, platform: str, now: datetime) -> dict:
        self.expire_inactive_sessions(now)
        self._require_active_pass(user_id)

        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is not None:
            return active

        now_iso = now.astimezone(UTC).isoformat()
        payload = {
            "session_id": f"ses_{uuid4().hex}",
            "user_id": user_id,
            "platform": platform,
            "status": "active",
            "entitlement_ref": self._subscription_repo.get_subscription_id(user_id),
            "sync_state": {
                "last_processed_pick": None,
                "sync_health": "healthy",
                "cursor": None,
            },
            "accepted_picks": [],
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_heartbeat_at": now_iso,
        }
        self._draft_session_repo.create_session(payload)
        return payload

    def resume_session(self, *, session_id: str, user_id: str, now: datetime) -> dict:
        self.expire_inactive_sessions(now)
        self._require_active_pass(user_id)
        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is None or active.get("session_id") != session_id:
            self._raise_if_terminal(session_id, user_id)
            raise LookupError("active session not found for user")

        self._draft_session_repo.resume_session(
            session_id=session_id,
            user_id=user_id,
            now=now,
        )
        resumed = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if resumed is None or resumed.get("session_id") != session_id:
            raise LookupError("active session not found for user")
        return resumed

    def expire_inactive_sessions(self, now: datetime) -> int:
        cutoff = now - self._inactivity_timeout
        return self._draft_session_repo.expire_inactive_sessions(cutoff)

    def end_session(self, *, session_id: str, user_id: str, now: datetime) -> None:
        self.expire_inactive_sessions(now)
        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is None or active.get("session_id") != session_id:
            raise LookupError("active session not found for user")
        self._draft_session_repo.end_session(
            session_id=session_id,
            user_id=user_id,
            now=now,
        )

    def get_sync_state(self, *, session_id: str, user_id: str, now: datetime) -> dict:
        self.expire_inactive_sessions(now)
        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is None or active.get("session_id") != session_id:
            self._raise_if_terminal(session_id, user_id)
            raise LookupError("active session not found for user")
        return active.get("sync_state", {})

    def attach_socket(self, *, session_id: str, user_id: str, now: datetime) -> dict:
        sync_state = self.get_sync_state(session_id=session_id, user_id=user_id, now=now)
        self._draft_session_repo.touch_heartbeat(
            session_id=session_id,
            user_id=user_id,
            now=now,
        )
        self._increment_counter("socket_attach")
        logger.info(
            "draft_session.socket_attach",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "sync_health": sync_state.get("sync_health"),
                "last_processed_pick": sync_state.get("last_processed_pick"),
            },
        )
        return sync_state

    def reconnect_sync_state(self, *, session_id: str, user_id: str, now: datetime) -> dict:
        self.expire_inactive_sessions(now)
        sync_state = self.get_sync_state(session_id=session_id, user_id=user_id, now=now)
        self._draft_session_repo.touch_heartbeat(
            session_id=session_id,
            user_id=user_id,
            now=now,
        )
        self._increment_counter("socket_reconnect")
        logger.info(
            "draft_session.socket_reconnect",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "sync_health": sync_state.get("sync_health"),
                "last_processed_pick": sync_state.get("last_processed_pick"),
            },
        )
        return sync_state

    def accept_pick(
        self,
        *,
        session_id: str,
        user_id: str,
        pick_number: int,
        now: datetime,
        ingestion_mode: str = "manual",
        player_id: str | None = None,
        player_name: str | None = None,
        player_lookup: dict[str, str | int | float | bool] | None = None,
    ) -> dict[str, dict | list]:
        self.expire_inactive_sessions(now)
        self._require_active_pass(user_id)
        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is None or active.get("session_id") != session_id:
            raise LookupError("active session not found for user")

        sync_state = dict(active.get("sync_state") or {})
        last_processed_pick = sync_state.get("last_processed_pick")
        expected_pick_number = (last_processed_pick or 0) + 1

        if pick_number < expected_pick_number:
            raise ValueError(
                f"pick_number {pick_number} already processed; expected {expected_pick_number}"
            )
        if pick_number > expected_pick_number:
            raise ValueError(
                f"pick_number {pick_number} out of turn; expected {expected_pick_number}"
            )

        platform = active.get("platform", "espn")
        accepted_picks = list(active.get("accepted_picks") or [])
        accepted_pick = {
            "pick_number": pick_number,
            "platform": platform,
            "ingestion_mode": ingestion_mode,
            "timestamp": now.astimezone(UTC).isoformat(),
        }
        if player_id is not None:
            accepted_pick["player_id"] = player_id
        if player_name is not None:
            accepted_pick["player_name"] = player_name
        if player_lookup is not None:
            accepted_pick["player_lookup"] = player_lookup
        elif player_id is not None:
            accepted_pick["player_lookup"] = {"player_id": player_id}
        else:
            accepted_pick["player_lookup"] = {"external_pick_number": pick_number}
        accepted_picks.append(accepted_pick)

        prior_sync_health = sync_state.get("sync_health", "healthy")
        sync_health = "healthy"
        recovered = prior_sync_health != "healthy" and sync_health == "healthy"

        updated_sync_state = {
            "sync_health": sync_health,
            "last_processed_pick": pick_number,
            "cursor": f"pk_{pick_number}",
        }

        if ingestion_mode == "manual":
            self._increment_counter("manual_fallback")
            logger.info(
                "draft_session.manual_fallback",
                extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "pick_number": pick_number,
                },
            )

        if recovered:
            self._increment_counter("sync_recovery")
            logger.info(
                "draft_session.sync_recovery",
                extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "pick_number": pick_number,
                },
            )

        self._draft_session_repo.update_session_progress(
            session_id=session_id,
            user_id=user_id,
            sync_state=updated_sync_state,
            accepted_picks=accepted_picks,
            now=now,
        )
        return {
            "sync_state": updated_sync_state,
            "accepted_pick": accepted_pick,
        }

    def get_observability_counters(self) -> dict[str, int]:
        return dict(self._observability_counters)

    def _increment_counter(self, name: str) -> None:
        self._observability_counters[name] = self._observability_counters.get(name, 0) + 1

    def _require_active_pass(self, user_id: str) -> None:
        if not self._subscription_repo.is_active(user_id):
            raise PermissionError("active draft pass required")

    def _raise_if_terminal(self, session_id: str, user_id: str) -> None:
        """Raise TerminalSessionError if the session exists but is in a terminal state."""
        row = self._draft_session_repo.get_session_by_id(session_id, user_id)
        if row is not None and row.get("status") in ("ended", "expired"):
            raise TerminalSessionError("session is closed")
