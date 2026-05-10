import { apiFetch } from "./index";

export interface SessionResponse {
  session_id: string;
  kit_id: string;
  status: string;
}

export interface SyncStateResponse {
  session_id: string;
  picks: PickRecord[];
  mode: string;
  status: string;
}

export interface PickRecord {
  player_id: string;
  player_name: string;
  round: number;
  pick_number: number;
  recorded_at: string;
}

export async function createSession(
  payload: { kitId: string; espnLeagueId?: string },
  token: string,
): Promise<SessionResponse> {
  return apiFetch<SessionResponse>("/draft-sessions/start", {
    method: "POST",
    body: JSON.stringify({
      kit_id: payload.kitId,
      espn_league_id: payload.espnLeagueId,
    }),
    token,
  });
}

export async function resumeSession(
  sessionId: string,
  token: string,
): Promise<SessionResponse> {
  return apiFetch<SessionResponse>(`/draft-sessions/${sessionId}/resume`, {
    method: "POST",
    token,
  });
}

export async function recordPick(
  sessionId: string,
  pick: { playerId: string; round: number; pickNumber: number },
  token: string,
): Promise<void> {
  return apiFetch<void>(`/draft-sessions/${sessionId}/manual-picks`, {
    method: "POST",
    body: JSON.stringify({
      player_id: pick.playerId,
      round: pick.round,
      pick_number: pick.pickNumber,
    }),
    token,
  });
}

export async function endSession(
  sessionId: string,
  token: string,
): Promise<void> {
  return apiFetch<void>(`/draft-sessions/${sessionId}/end`, {
    method: "POST",
    token,
  });
}

export async function fetchSyncState(
  sessionId: string,
  token: string,
): Promise<SyncStateResponse> {
  return apiFetch<SyncStateResponse>(`/draft-sessions/${sessionId}/sync-state`, {
    token,
  });
}
