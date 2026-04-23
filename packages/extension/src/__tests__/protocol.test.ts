import {
  OBSERVABILITY_SIGNALS,
  OPTIONAL_CLIENT_EVENT_TYPES,
  OPTIONAL_SERVER_EVENT_TYPES,
  REQUIRED_CLIENT_EVENT_TYPES,
  REQUIRED_SERVER_EVENT_TYPES,
  isPickPayload,
  isSyncStatePayload,
} from "../shared/protocol";

describe("shared protocol contract", () => {
  it("defines required websocket event types", () => {
    expect(REQUIRED_CLIENT_EVENT_TYPES).toEqual(["pick", "sync_state"]);
    expect(REQUIRED_SERVER_EVENT_TYPES).toEqual(["state_update", "error"]);
  });

  it("defines optional suggestion event types", () => {
    expect(OPTIONAL_CLIENT_EVENT_TYPES).toEqual(["get_suggestions"]);
    expect(OPTIONAL_SERVER_EVENT_TYPES).toEqual(["suggestions"]);
  });

  it("does not define MANUAL_PICK as websocket event", () => {
    expect(REQUIRED_CLIENT_EVENT_TYPES).not.toContain("manual_pick");
    expect(OPTIONAL_CLIENT_EVENT_TYPES).not.toContain("manual_pick");
  });

  it("validates sync_state payload shape", () => {
    expect(isSyncStatePayload({ session_id: "session-123" })).toBe(true);
    expect(isSyncStatePayload({ sessionId: "session-123" })).toBe(false);
    expect(isSyncStatePayload({ session_id: 123 })).toBe(false);
  });

  it("validates minimal pick payload shape", () => {
    expect(isPickPayload({ player_name: "Auston Matthews" })).toBe(true);
    expect(isPickPayload({ player_name: "Auston Matthews", pick_number: 7 })).toBe(true);
    expect(isPickPayload({ player_name: 7 })).toBe(false);
    expect(isPickPayload({})).toBe(false);
  });

  it("rejects NaN and Infinity as pick_number", () => {
    expect(isPickPayload({ player_name: "Auston Matthews", pick_number: NaN })).toBe(false);
    expect(isPickPayload({ player_name: "Auston Matthews", pick_number: Infinity })).toBe(false);
    expect(isPickPayload({ player_name: "Auston Matthews", pick_number: -Infinity })).toBe(false);
  });

  it("observability: declares required signal categories", () => {
    expect(OBSERVABILITY_SIGNALS).toEqual(
      expect.arrayContaining([
        "socket_attach_success",
        "socket_attach_failure",
        "socket_open",
        "socket_close",
        "socket_reconnect_attempt",
        "sync_recovery",
        "sync_desync",
        "selector_fallback",
        "manual_fallback_activated",
      ]),
    );
  });
});
