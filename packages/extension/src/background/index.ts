type RuntimeMessage =
  | {
      type: "PICK_DETECTED";
      playerName: string;
      pickNumber?: number;
    }
  | { type: "SYNC_DESYNC" }
  | {
      type: string;
      [key: string]: unknown;
    };

type SocketLike = {
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  readyState: number;
  send: (payload: string) => void;
  close: () => void;
};

type SocketConstructor = new (url: string) => SocketLike;
const SOCKET_OPEN_STATE = 1;

type BackgroundSessionBridgeDeps = {
  WebSocketImpl: SocketConstructor;
  getToken: () => Promise<string | undefined>;
  setTimeoutImpl?: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>;
  onMetric?: (event: { type: string; detail?: string | number }) => void;
};

export class BackgroundSessionBridge {
  private readonly WebSocketImpl: SocketConstructor;
  private readonly getToken: () => Promise<string | undefined>;
  private readonly setTimeoutImpl: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>;
  private readonly onMetric: (event: { type: string; detail?: string | number }) => void;

  private socket: SocketLike | null = null;
  private sessionId: string | null = null;
  private wsUrl: string | null = null;
  private reconnectDelayMs = 1000;
  private hasConnected = false;
  private stopReconnect = false;
  private _cancelCurrentReconnect: (() => void) | null = null;

  constructor(deps: BackgroundSessionBridgeDeps) {
    this.WebSocketImpl = deps.WebSocketImpl;
    this.getToken = deps.getToken;
    this.setTimeoutImpl = deps.setTimeoutImpl ?? setTimeout;
    this.onMetric = deps.onMetric ?? (() => undefined);
  }

  async initSession(params: { sessionId: string; wsUrl: string }): Promise<void> {
    this._cancelCurrentReconnect?.();
    this.socket?.close();
    this.sessionId = params.sessionId;
    this.wsUrl = params.wsUrl;
    this.reconnectDelayMs = 1000;
    this.hasConnected = false;
    this.stopReconnect = false;
    await this.connect();
  }

  handleRuntimeMessage(message: RuntimeMessage): void {
    if (message.type === "PICK_DETECTED" && this.socket?.readyState === SOCKET_OPEN_STATE) {
      this.socket.send(
        JSON.stringify({
          type: "pick",
          payload: {
            player_name: message.playerName,
            pick_number: message.pickNumber,
          },
        }),
      );
    } else if (message.type === "SYNC_DESYNC") {
      this.onMetric({ type: "sync_desync" });
    }
  }

  private async connect(): Promise<void> {
    if (!this.wsUrl) {
      return;
    }

    const token = await this.getToken();
    const socketUrl = token ? `${this.wsUrl}?token=${token}` : this.wsUrl;

    const socket = new this.WebSocketImpl(socketUrl);
    this.socket = socket;

    let cancelled = false;
    this._cancelCurrentReconnect = () => {
      cancelled = true;
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as {
          type?: string;
          payload?: { message?: string; code?: string };
        };
        if (message.type === "error" && message.payload?.code === "SESSION_CLOSED") {
          this.stopReconnect = true;
        }
      } catch {
        // Ignore non-JSON messages; reconnect policy only cares about structured terminal denial.
      }
    };

    socket.onopen = () => {
      this.reconnectDelayMs = 1000;
      this.onMetric({ type: "socket_attach_success" });
      this.onMetric({ type: "socket_open" });

      if (this.sessionId) {
        socket.send(JSON.stringify({ type: "sync_state", session_id: this.sessionId }));

        if (this.hasConnected) {
          this.onMetric({ type: "sync_recovery" });
        }
      }

      this.hasConnected = true;
    };

    socket.onclose = () => {
      this.socket = null;
      this.onMetric({ type: "socket_close" });

      if (this.stopReconnect || cancelled) {
        return;
      }

      const currentDelay = this.reconnectDelayMs;
      this.onMetric({ type: "socket_reconnect_attempt", detail: currentDelay });
      this.setTimeoutImpl(() => {
        if (cancelled) {
          return;
        }
        void this.connect();
      }, currentDelay);

      this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, 30_000);
    };

    socket.onerror = () => {
      this.onMetric({ type: "socket_attach_failure" });
      socket.close();
    };
  }
}

export function startBackgroundServiceWorker(): void {
  const bridge = new BackgroundSessionBridge({
    WebSocketImpl: WebSocket as unknown as SocketConstructor,
    getToken: async () => {
      const result = await chrome.storage.local.get("authToken");
      return result.authToken as string | undefined;
    },
    onMetric: (event) => console.log("[pucklogic:metric]", event.type, event.detail ?? ""),
  });

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === "INIT_SESSION") {
      void bridge
        .initSession({ sessionId: message.sessionId as string, wsUrl: message.wsUrl as string })
        .then(() => {
          sendResponse({ ok: true });
        })
        .catch((err: unknown) => {
          sendResponse({ ok: false, error: String(err) });
        });
      return true; // keep channel open for async response
    }

    bridge.handleRuntimeMessage(message as RuntimeMessage);
  });
}

// Top-level service-worker entry point — only runs in the actual extension context
if (typeof chrome !== "undefined" && chrome.runtime?.id) {
  startBackgroundServiceWorker();
}
