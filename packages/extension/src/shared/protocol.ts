export const REQUIRED_CLIENT_EVENT_TYPES = ["pick", "sync_state"] as const;
export const REQUIRED_SERVER_EVENT_TYPES = ["state_update", "error"] as const;

export const OPTIONAL_CLIENT_EVENT_TYPES = ["get_suggestions"] as const;
export const OPTIONAL_SERVER_EVENT_TYPES = ["suggestions"] as const;

export const OBSERVABILITY_SIGNALS = [
  "socket_attach_success",
  "socket_attach_failure",
  "socket_open",
  "socket_close",
  "socket_reconnect_attempt",
  "sync_recovery",
  "sync_desync",
  "selector_fallback",
  "manual_fallback_activated",
] as const;

export type ObservabilitySignal = (typeof OBSERVABILITY_SIGNALS)[number];

export type RequiredClientEventType = (typeof REQUIRED_CLIENT_EVENT_TYPES)[number];
export type RequiredServerEventType = (typeof REQUIRED_SERVER_EVENT_TYPES)[number];

export type OptionalClientEventType = (typeof OPTIONAL_CLIENT_EVENT_TYPES)[number];
export type OptionalServerEventType = (typeof OPTIONAL_SERVER_EVENT_TYPES)[number];

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null;
}

export function isSyncStatePayload(value: unknown): value is { session_id: string } {
  if (!isRecord(value)) {
    return false;
  }

  return typeof value.session_id === "string";
}

export function isPickPayload(value: unknown): value is { player_name: string; pick_number?: number } {
  if (!isRecord(value)) {
    return false;
  }

  if (typeof value.player_name !== "string") {
    return false;
  }

  if (value.pick_number === undefined) {
    return true;
  }

  return typeof value.pick_number === "number";
}
