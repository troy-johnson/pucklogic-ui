import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BackgroundSessionBridge } from "../background";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 3;

  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  readonly sent: string[] = [];
  readonly url: string;
  readyState = FakeWebSocket.CONNECTING;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(payload: string): void {
    this.sent.push(payload);
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }

  triggerOpen(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  triggerError(): void {
    this.onerror?.();
  }
}

describe("BackgroundSessionBridge", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("forwards PICK_DETECTED as pick websocket event", async () => {
    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-123",
    });

    await bridge.initSession({
      sessionId: "session-123",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-123/ws",
    });

    const socket = FakeWebSocket.instances[0];
    socket.triggerOpen();

    bridge.handleRuntimeMessage({
      type: "PICK_DETECTED",
      playerName: "Connor McDavid",
      pickNumber: 1,
    });

    expect(socket.sent).toContain(
      JSON.stringify({ type: "pick", payload: { player_name: "Connor McDavid", pick_number: 1 } }),
    );
  });

  it("does not forward PICK_DETECTED before websocket open", async () => {
    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-123",
    });

    await bridge.initSession({
      sessionId: "session-123",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-123/ws",
    });

    const socket = FakeWebSocket.instances[0];

    bridge.handleRuntimeMessage({
      type: "PICK_DETECTED",
      playerName: "Connor McDavid",
      pickNumber: 1,
    });

    expect(socket.sent).toEqual([]);
  });

  it("requests sync_state on websocket open", async () => {
    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-abc",
    });

    await bridge.initSession({
      sessionId: "session-xyz",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-xyz/ws",
    });

    const socket = FakeWebSocket.instances[0];
    socket.triggerOpen();

    expect(socket.sent).toContain(JSON.stringify({ type: "sync_state", session_id: "session-xyz" }));
  });

  it("reconnects with exponential backoff after close", async () => {
    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-reconnect",
    });

    await bridge.initSession({
      sessionId: "session-r",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-r/ws",
    });

    const firstSocket = FakeWebSocket.instances[0];
    firstSocket.close();

    expect(FakeWebSocket.instances).toHaveLength(1);

    vi.advanceTimersByTime(1000);
    await vi.runAllTimersAsync();
    expect(FakeWebSocket.instances).toHaveLength(2);

    const secondSocket = FakeWebSocket.instances[1];
    secondSocket.close();

    vi.advanceTimersByTime(2000);
    await vi.runAllTimersAsync();
    expect(FakeWebSocket.instances).toHaveLength(3);
  });

  it("observability: emits attach/open/close and reconnect recovery signals", async () => {
    const metrics: string[] = [];

    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-obs",
      onMetric: (event) => metrics.push(event.type),
    });

    await bridge.initSession({
      sessionId: "session-obs",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-obs/ws",
    });

    const firstSocket = FakeWebSocket.instances[0];
    firstSocket.triggerOpen();
    firstSocket.close();

    vi.advanceTimersByTime(1000);
    await vi.runAllTimersAsync();

    const secondSocket = FakeWebSocket.instances[1];
    secondSocket.triggerOpen();

    expect(metrics).toEqual(
      expect.arrayContaining([
        "socket_attach_success",
        "socket_open",
        "socket_close",
        "socket_reconnect_attempt",
        "sync_recovery",
      ]),
    );
  });

  it("observability: emits attach success only after socket opens", async () => {
    const metrics: string[] = [];

    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-obs",
      onMetric: (event) => metrics.push(event.type),
    });

    await bridge.initSession({
      sessionId: "session-obs",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-obs/ws",
    });

    expect(metrics).not.toContain("socket_attach_success");

    const socket = FakeWebSocket.instances[0];
    socket.triggerOpen();

    expect(metrics).toContain("socket_attach_success");
  });

  it("observability: emits sync_desync metric when SYNC_DESYNC message received", () => {
    const metrics: string[] = [];

    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => undefined,
      onMetric: (event) => metrics.push(event.type),
    });

    bridge.handleRuntimeMessage({ type: "SYNC_DESYNC" });

    expect(metrics).toContain("sync_desync");
  });

  it("observability: emits attach failure signal on socket error", async () => {
    const metrics: string[] = [];

    const bridge = new BackgroundSessionBridge({
      WebSocketImpl: FakeWebSocket,
      getToken: async () => "token-err",
      onMetric: (event) => metrics.push(event.type),
    });

    await bridge.initSession({
      sessionId: "session-err",
      wsUrl: "wss://api.pucklogic.com/draft-sessions/session-err/ws",
    });

    const socket = FakeWebSocket.instances[0];
    socket.triggerError();

    expect(metrics).toContain("socket_attach_failure");
  });
});
