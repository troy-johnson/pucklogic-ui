type RuntimeMessage =
  | {
      type: "PICK_DETECTED";
      playerName: string;
      pickNumber?: number;
    }
  | {
      type: string;
      [key: string]: unknown;
    };

type SocketLike = {
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  send: (payload: string) => void;
  close: () => void;
};

type SocketConstructor = new (url: string) => SocketLike;

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

  constructor(deps: BackgroundSessionBridgeDeps) {
    this.WebSocketImpl = deps.WebSocketImpl;
    this.getToken = deps.getToken;
    this.setTimeoutImpl = deps.setTimeoutImpl ?? setTimeout;
    this.onMetric = deps.onMetric ?? (() => undefined);
  }

  async initSession(params: { sessionId: string; wsUrl: string }): Promise<void> {
    this.sessionId = params.sessionId;
    this.wsUrl = params.wsUrl;
    await this.connect();
  }

  handleRuntimeMessage(message: RuntimeMessage): void {
    if (message.type === "PICK_DETECTED") {
      this.socket?.send(
        JSON.stringify({
          type: "pick",
          player_name: message.playerName,
          pick_number: message.pickNumber,
        }),
      );
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
    this.onMetric({ type: "socket_attach_success" });

    socket.onopen = () => {
      this.reconnectDelayMs = 1000;
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

      const currentDelay = this.reconnectDelayMs;
      this.onMetric({ type: "socket_reconnect_attempt", detail: currentDelay });
      this.setTimeoutImpl(() => {
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
