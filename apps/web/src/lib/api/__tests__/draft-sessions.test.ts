import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/index", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api/index";
import {
  createSession,
  endSession,
  fetchSyncState,
  recordPick,
  resumeSession,
} from "@/lib/api/draft-sessions";

afterEach(() => vi.clearAllMocks());

const TOKEN = "test-token";
const SESSION_ID = "sess-123";

describe("createSession", () => {
  it("POSTs to /draft-sessions/start", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ session_id: SESSION_ID });
    await createSession({ kitId: "kit-1" }, TOKEN);
    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith(
      "/draft-sessions/start",
      expect.objectContaining({ method: "POST", token: TOKEN }),
    );
  });
});

describe("resumeSession", () => {
  it("POSTs to /draft-sessions/{id}/resume", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ session_id: SESSION_ID });
    await resumeSession(SESSION_ID, TOKEN);
    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith(
      `/draft-sessions/${SESSION_ID}/resume`,
      expect.objectContaining({ method: "POST", token: TOKEN }),
    );
  });
});

describe("recordPick", () => {
  it("POSTs to /draft-sessions/{id}/manual-picks", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ok: true });
    const pick = { playerId: "p1", round: 1, pickNumber: 3 };
    await recordPick(SESSION_ID, pick, TOKEN);
    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith(
      `/draft-sessions/${SESSION_ID}/manual-picks`,
      expect.objectContaining({ method: "POST", token: TOKEN }),
    );
  });
});

describe("endSession", () => {
  it("POSTs to /draft-sessions/{id}/end", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    await endSession(SESSION_ID, TOKEN);
    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith(
      `/draft-sessions/${SESSION_ID}/end`,
      expect.objectContaining({ method: "POST", token: TOKEN }),
    );
  });
});

describe("fetchSyncState", () => {
  it("GETs /draft-sessions/{id}/sync-state", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ picks: [] });
    await fetchSyncState(SESSION_ID, TOKEN);
    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith(
      `/draft-sessions/${SESSION_ID}/sync-state`,
      expect.objectContaining({ token: TOKEN }),
    );
    const call = vi.mocked(apiFetch).mock.calls[0][1] as Record<string, unknown>;
    expect(call.method ?? "GET").toBe("GET");
  });
});
