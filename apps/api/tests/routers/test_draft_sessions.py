"""Integration tests for live draft session router."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core import dependencies
from core.dependencies import get_current_user, get_draft_session_service
from main import app
from services.draft_sessions import TerminalSessionError

MOCK_USER = {"id": "usr_123", "email": "user@example.com"}
START_BODY = {
    "platform": "espn",
    "season": "2026-27",
    "league_profile_id": "lp_123",
    "scoring_config_id": "sc_123",
    "source_weights": {"hashtag": 1.0},
}


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock()


@pytest.fixture(autouse=True)
def override_deps(mock_service: MagicMock) -> Iterator[None]:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_draft_session_service] = lambda: mock_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def stub_supabase_auth(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        dependencies,
        "get_db",
        lambda: SimpleNamespace(
            auth=SimpleNamespace(
                get_user=lambda token: SimpleNamespace(
                    user=SimpleNamespace(id="usr_123", email="user@example.com")
                )
                if token == "ws-token"
                else SimpleNamespace(user=None)
            )
        ),
    )
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestStartDraftSession:
    def test_start_returns_200_with_session_payload(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.start_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_123",
            "platform": "espn",
            "status": "active",
            "sync_state": {"sync_health": "healthy"},
        }

        response = client.post("/draft-sessions/start", json=START_BODY)

        assert response.status_code == 200
        assert response.json()["session_id"] == "ses_1"
        assert response.json()["platform"] == "espn"

    def test_start_uses_authenticated_user_id(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.start_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_123",
            "platform": "espn",
            "status": "active",
            "sync_state": {"sync_health": "healthy"},
        }

        client.post("/draft-sessions/start", json=START_BODY)

        kwargs = mock_service.start_session.call_args.kwargs
        assert kwargs["user_id"] == "usr_123"
        assert kwargs["platform"] == "espn"
        assert kwargs["season"] == "2026-27"
        assert kwargs["league_profile_id"] == "lp_123"
        assert kwargs["scoring_config_id"] == "sc_123"
        assert kwargs["source_weights"] == {"hashtag": 1.0}

    def test_start_returns_403_without_entitlement(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.start_session.side_effect = PermissionError("active draft pass required")

        response = client.post("/draft-sessions/start", json=START_BODY)

        assert response.status_code == 403


class TestTerminalSessionReconnectDenial:
    def test_resume_returns_409_for_terminal_session(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.resume_session.side_effect = TerminalSessionError("session is closed")

        response = client.post("/draft-sessions/ses_1/resume")

        assert response.status_code == 409
        assert "closed" in response.json()["detail"]

    def test_connect_emits_session_closed_error_when_terminal(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.side_effect = TerminalSessionError("session is closed")

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            event = ws.receive_json()

        assert event["type"] == "error"
        assert event["payload"]["code"] == "SESSION_CLOSED"
        assert "closed" in event["payload"]["message"]


class TestWebSocketTerminalInLoop:
    def test_pick_event_sends_session_closed_code_and_closes_socket(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.side_effect = TerminalSessionError("session is closed")

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": {"pick_number": 1}})
            event = ws.receive_json()

        assert event["type"] == "error"
        assert event["payload"]["code"] == "SESSION_CLOSED"
        assert "closed" in event["payload"]["message"]

    def test_sync_state_event_sends_session_closed_code_and_closes_socket(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.reconnect_sync_state.side_effect = TerminalSessionError("session is closed")

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "sync_state"})
            event = ws.receive_json()

        assert event["type"] == "error"
        assert event["payload"]["code"] == "SESSION_CLOSED"
        assert "closed" in event["payload"]["message"]


class TestResumeDraftSession:
    def test_resume_returns_200(self, client: TestClient, mock_service: MagicMock) -> None:
        mock_service.resume_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_123",
            "platform": "espn",
            "status": "active",
            "sync_state": {"sync_health": "healthy"},
        }

        response = client.post("/draft-sessions/ses_1/resume")

        assert response.status_code == 200
        assert response.json()["session_id"] == "ses_1"

    def test_resume_returns_404_when_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.resume_session.side_effect = LookupError("active session not found for user")

        response = client.post("/draft-sessions/ses_1/resume")

        assert response.status_code == 404

    def test_resume_returns_403_when_entitlement_inactive(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.resume_session.side_effect = PermissionError(
            "active subscription required to reconnect"
        )

        response = client.post("/draft-sessions/ses_1/resume")

        assert response.status_code == 403
        assert "subscription" in response.json()["detail"]


class TestEndDraftSession:
    def test_end_returns_204(self, client: TestClient, mock_service: MagicMock) -> None:
        response = client.post("/draft-sessions/ses_1/end")

        assert response.status_code == 204
        mock_service.end_session.assert_called_once()

    def test_end_returns_409_for_terminal_session(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.end_session.side_effect = TerminalSessionError("session is closed")

        response = client.post("/draft-sessions/ses_1/end")

        assert response.status_code == 409
        assert "closed" in response.json()["detail"]


class TestSyncState:
    def test_get_sync_state_returns_payload(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.get_sync_state.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 18,
        }

        response = client.get("/draft-sessions/ses_1/sync-state")

        assert response.status_code == 200
        assert response.json()["sync_health"] == "healthy"
        kwargs = mock_service.get_sync_state.call_args.kwargs
        assert kwargs["session_id"] == "ses_1"
        assert kwargs["user_id"] == "usr_123"

    def test_get_sync_state_returns_404_when_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.get_sync_state.side_effect = LookupError("active session not found for user")

        response = client.get("/draft-sessions/ses_1/sync-state")

        assert response.status_code == 404
        assert response.json()["detail"] == "active session not found for user"

    def test_get_sync_state_returns_409_for_terminal_session(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.get_sync_state.side_effect = TerminalSessionError("session is closed")

        response = client.get("/draft-sessions/ses_1/sync-state")

        assert response.status_code == 409
        assert "closed" in response.json()["detail"]


class TestManualPickEndpoint:
    def test_manual_pick_returns_state_update_payload(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.accept_pick.return_value = {
            "sync_state": {
                "sync_health": "healthy",
                "last_processed_pick": 19,
                "cursor": "pk_19",
            },
            "accepted_pick": {
                "pick_number": 19,
                "platform": "espn",
                "ingestion_mode": "manual",
                "timestamp": "2026-04-11T12:00:00+00:00",
                "player_id": "8478402",
                "player_lookup": {"espn_player_id": "8478402"},
            },
        }

        response = client.post(
            "/draft-sessions/ses_1/manual-picks",
            json={"pick_number": 19, "player_id": "8478402"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["sync_state"]["last_processed_pick"] == 19
        assert body["accepted_pick"]["pick_number"] == 19
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["session_id"] == "ses_1"
        assert kwargs["user_id"] == "usr_123"
        assert kwargs["pick_number"] == 19
        assert kwargs["player_id"] == "8478402"

    def test_manual_pick_passes_player_identity_to_service(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.accept_pick.return_value = {
            "sync_state": {
                "sync_health": "healthy",
                "last_processed_pick": 19,
                "cursor": "pk_19",
            },
            "accepted_pick": {
                "pick_number": 19,
                "platform": "espn",
                "ingestion_mode": "manual",
                "timestamp": "2026-04-11T12:00:00+00:00",
                "player_name": "Connor McDavid",
                "player_lookup": {"espn_player_id": "8478402"},
            },
        }

        response = client.post(
            "/draft-sessions/ses_1/manual-picks",
            json={
                "pick_number": 19,
                "player_name": "Connor McDavid",
                "player_lookup": {"espn_player_id": "8478402"},
            },
        )

        assert response.status_code == 200
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["player_name"] == "Connor McDavid"
        assert kwargs["player_lookup"] == {"espn_player_id": "8478402"}

    def test_manual_pick_returns_409_for_out_of_turn_pick(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.accept_pick.side_effect = ValueError("pick_number 22 out of turn; expected 20")

        response = client.post(
            "/draft-sessions/ses_1/manual-picks",
            json={"pick_number": 22, "player_name": "Skater"},
        )

        assert response.status_code == 409

    def test_manual_pick_returns_403_without_entitlement(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.accept_pick.side_effect = PermissionError("active draft pass required")

        response = client.post(
            "/draft-sessions/ses_1/manual-picks",
            json={"pick_number": 19, "player_name": "Skater"},
        )

        assert response.status_code == 403

    def test_manual_pick_returns_409_for_terminal_session(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.accept_pick.side_effect = TerminalSessionError("session is closed")

        response = client.post(
            "/draft-sessions/ses_1/manual-picks",
            json={"pick_number": 19, "player_name": "Skater"},
        )

        assert response.status_code == 409


class TestDraftSessionWebSocket:
    def test_connect_emits_sync_state_event(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 22,
            "cursor": "pk_22",
        }

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            event = ws.receive_json()

        assert event["type"] == "sync_state"
        assert event["payload"]["last_processed_pick"] == 22
        kwargs = mock_service.attach_socket.call_args.kwargs
        assert kwargs["session_id"] == "ses_1"
        assert kwargs["user_id"] == "usr_123"

    def test_connect_uses_query_token_for_browser_websocket_auth(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 22,
            "cursor": "pk_22",
        }

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            event = ws.receive_json()

        assert event["type"] == "sync_state"
        kwargs = mock_service.attach_socket.call_args.kwargs
        assert kwargs["user_id"] == "usr_123"

    def test_connect_rejects_missing_query_token(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        with client.websocket_connect("/draft-sessions/ses_1/ws") as ws:
            event = ws.receive_json()

        assert event["type"] == "error"
        assert "Missing or invalid token" in event["payload"]["message"]

    def test_connect_rejects_invalid_query_token(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        with client.websocket_connect("/draft-sessions/ses_1/ws?token=bad-token") as ws:
            event = ws.receive_json()

        assert event["type"] == "error"
        assert "Invalid token" in event["payload"]["message"]
        mock_service.attach_socket.assert_not_called()
        mock_service.attach_socket.assert_not_called()

    def test_connect_emits_error_event_when_session_missing(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.side_effect = LookupError("active session not found for user")

        with client.websocket_connect("/draft-sessions/ses_404/ws?token=ws-token") as ws:
            event = ws.receive_json()

        assert event["type"] == "error"
        assert "not found" in event["payload"]["message"]

    def test_pick_event_receives_state_update(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 10,
            "cursor": None,
        }
        mock_service.accept_pick.return_value = {
            "sync_state": {
                "sync_health": "healthy",
                "last_processed_pick": 11,
                "cursor": None,
            },
            "accepted_pick": {
                "pick_number": 11,
                "platform": "espn",
                "ingestion_mode": "auto",
                "timestamp": "2026-04-25T00:00:00+00:00",
            },
        }

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": {"pick_number": 11}})
            event = ws.receive_json()

        assert event["type"] == "state_update"
        assert event["payload"]["status"] == "pick_received"
        assert event["payload"]["sync_state"]["last_processed_pick"] == 11
        assert event["payload"]["pick_number"] == 11
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["session_id"] == "ses_1"
        assert kwargs["user_id"] == "usr_123"
        assert kwargs["pick_number"] == 11
        assert kwargs["ingestion_mode"] == "auto"

    def test_pick_event_rejects_duplicate_pick_number(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 10,
            "cursor": None,
        }
        mock_service.accept_pick.side_effect = ValueError(
            "pick_number 10 already processed; expected 11"
        )

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": {"pick_number": 10}})
            event = ws.receive_json()

        assert event["type"] == "error"
        assert "already processed" in event["payload"]["message"]

    def test_pick_event_rejects_out_of_turn_pick_number(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 10,
            "cursor": None,
        }
        mock_service.accept_pick.side_effect = ValueError("pick_number 13 out of turn; expected 11")

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": {"pick_number": 13}})
            event = ws.receive_json()

        assert event["type"] == "error"
        assert "out of turn" in event["payload"]["message"]

    def test_sync_state_event_uses_reconnect_flow(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 30,
            "cursor": "pk_30",
        }
        mock_service.reconnect_sync_state.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 31,
            "cursor": "pk_31",
        }

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "sync_state"})
            event = ws.receive_json()

        assert event["type"] == "sync_state"
        assert event["payload"]["last_processed_pick"] == 31
        kwargs = mock_service.reconnect_sync_state.call_args.kwargs
        assert kwargs["session_id"] == "ses_1"
        assert kwargs["user_id"] == "usr_123"

    def test_sync_state_event_emits_error_when_reconnect_denied(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 30,
            "cursor": "pk_30",
        }
        mock_service.reconnect_sync_state.side_effect = PermissionError(
            "active draft pass required"
        )

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "sync_state"})
            event = ws.receive_json()

        assert event["type"] == "error"
        assert "active draft pass required" in event["payload"]["message"]


class TestWebSocketPickNumberNormalization:
    """pick_number is optional in the WS auto-ingestion path."""

    def _make_service_result(self, pick_number: int) -> dict:
        return {
            "sync_state": {
                "sync_health": "healthy",
                "last_processed_pick": pick_number,
                "cursor": f"pk_{pick_number}",
            },
            "accepted_pick": {
                "pick_number": pick_number,
                "platform": "espn",
                "ingestion_mode": "auto",
                "timestamp": "2026-04-25T00:00:00+00:00",
            },
        }

    def test_pick_without_pick_number_is_accepted(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.return_value = self._make_service_result(1)

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": {"player_name": "Connor McDavid"}})
            event = ws.receive_json()

        assert event["type"] == "state_update"
        assert event["payload"]["status"] == "pick_received"
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["pick_number"] is None

    def test_pick_without_pick_number_emits_derived_value_in_state_update(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.return_value = self._make_service_result(7)

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": {"player_name": "Auston Matthews"}})
            event = ws.receive_json()

        assert event["payload"]["pick_number"] == 7

    def test_pick_with_zero_pick_number_is_treated_as_absent(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.return_value = self._make_service_result(1)

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": {"player_name": "Skater", "pick_number": 0}})
            event = ws.receive_json()

        assert event["type"] == "state_update"
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["pick_number"] is None

    def test_pick_with_negative_pick_number_is_treated_as_absent(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.return_value = self._make_service_result(1)

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json(
                {
                    "type": "pick",
                    "payload": {"player_name": "Skater", "pick_number": -5},
                }
            )
            event = ws.receive_json()

        assert event["type"] == "state_update"
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["pick_number"] is None

    def test_pick_with_string_pick_number_is_treated_as_absent(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.return_value = self._make_service_result(1)

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json(
                {
                    "type": "pick",
                    "payload": {"player_name": "Skater", "pick_number": "7"},
                }
            )
            event = ws.receive_json()

        assert event["type"] == "state_update"
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["pick_number"] is None

    def test_pick_with_true_pick_number_is_treated_as_absent(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.return_value = self._make_service_result(1)

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json(
                {
                    "type": "pick",
                    "payload": {"player_name": "Skater", "pick_number": True},
                }
            )
            event = ws.receive_json()

        assert event["type"] == "state_update"
        assert event["payload"]["pick_number"] == 1
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["pick_number"] is None

    def test_pick_with_false_pick_number_is_treated_as_absent(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.return_value = self._make_service_result(1)

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json(
                {
                    "type": "pick",
                    "payload": {"player_name": "Skater", "pick_number": False},
                }
            )
            event = ws.receive_json()

        assert event["type"] == "state_update"
        assert event["payload"]["pick_number"] == 1
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["pick_number"] is None

    def test_pick_with_non_dict_payload_does_not_crash(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.return_value = self._make_service_result(1)

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": ["bad", "payload"]})
            event = ws.receive_json()

        assert event["type"] == "state_update"
        kwargs = mock_service.accept_pick.call_args.kwargs
        assert kwargs["pick_number"] is None

    def test_explicit_valid_pick_number_still_enforces_ordering(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.attach_socket.return_value = {"sync_health": "healthy"}
        mock_service.accept_pick.side_effect = ValueError("pick_number 5 out of turn; expected 3")

        with client.websocket_connect("/draft-sessions/ses_1/ws?token=ws-token") as ws:
            ws.receive_json()
            ws.send_json({"type": "pick", "payload": {"player_name": "Skater", "pick_number": 5}})
            event = ws.receive_json()

        assert event["type"] == "error"
        assert "out of turn" in event["payload"]["message"]


class TestManualPickStrictContract:
    """Manual HTTP endpoint must still require a positive integer pick_number."""

    def test_manual_pick_requires_pick_number(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        response = client.post(
            "/draft-sessions/ses_1/manual-picks",
            json={"player_name": "Connor McDavid"},
        )

        assert response.status_code == 422
        mock_service.accept_pick.assert_not_called()
