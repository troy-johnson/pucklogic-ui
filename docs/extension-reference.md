# PuckLogic — Extension Reference

**Domain:** Chrome MV3 extension (`packages/extension/`)
**See also:** [pucklogic-architecture.md](pucklogic-architecture.md) for system overview

---

## 1. Project Structure

```
packages/extension/
├── manifest.json                  # MV3 manifest
├── package.json                   # Workspace package + scripts
├── tsconfig.json                  # TypeScript config
├── vitest.config.ts               # Test config
├── src/
│   ├── background/
│   │   └── index.ts               # Background/session bridge
│   ├── content/
│   │   ├── espn.ts                # ESPN Fantasy adapter
│   │   ├── yahoo.ts               # Yahoo Fantasy adapter
│   │   └── manualFallback.ts      # Selector-failure/manual-mode escalation helper
│   ├── shared/
│   │   └── protocol.ts            # Shared protocol/event primitives
│   └── __tests__/                 # Vitest coverage for protocol/background/adapters/fallback
└── dist/                          # Build output
```

`008c` currently covers the sync-adapter/runtime foundation (background bridge, content adapters, protocol, fallback, observability). A richer popup/sidebar UX is owned by later web/extension workflow work and should not be assumed to exist yet.

---

## 2. Chrome MV3 Manifest

```json
{
  "manifest_version": 3,
  "name": "PuckLogic Draft Monitor",
  "version": "1.0.0",
  "description": "Real-time best-available suggestions for your fantasy hockey draft",
  "permissions": ["storage", "tabs"],
  "host_permissions": [
    "https://*.espn.com/*",
    "https://*.yahoo.com/*"
  ],
  "background": {
    "service_worker": "service-worker.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": [
        "https://fantasy.espn.com/*/draft*",
        "https://basketball.fantasysports.yahoo.com/hockey/*/draft*"
      ],
      "js": ["content-script.js"],
      "run_at": "document_idle"
    }
  ],
  "action": {
    "default_popup": "popup.html",
    "default_title": "PuckLogic"
  },
  "icons": {
    "16": "icons/icon-16.png",
    "48": "icons/icon-48.png",
    "128": "icons/icon-128.png"
  }
}
```

**Security:** No `eval`, no `unsafe-inline`. All code must comply with MV3 CSP. `type: "module"` on service worker enables ES module imports.

---

## 3. Build Configuration

`packages/extension` uses a **minimal Vite + Vitest** setup suitable for MV3 packaging in the monorepo. The current launch-path implementation is intentionally narrow:

- background entry: `src/background/index.ts`
- content/runtime entries: `src/content/espn.ts`, `src/content/yahoo.ts`, `src/content/manualFallback.ts`
- shared protocol primitives: `src/shared/protocol.ts`
- focused tests under `src/__tests__/`

If popup/sidebar UI entries are added later, update this section to reflect the actual packaged entrypoints instead of documenting planned-but-unimplemented surfaces.

---

## 4. Platform Adapter Pattern

All platform-specific pick detection lives in adapters. The content script selects the adapter based on `window.location.hostname`.

```typescript
// packages/extension/src/adapters/types.ts
interface PlatformAdapter {
  detectPicks(callback: (pick: Pick) => void): void;
  extractPlayerName(element: HTMLElement): string | null;
  getDraftRoomState(): DraftState;
  getLeagueConfig(): LeagueConfig;
  cleanup(): void;
}

interface Pick {
  pickNumber: number;
  playerName: string;
  team?: string;
  position?: string;
}

interface DraftState {
  round: number;
  pick: number;
  totalPicks: number;
  myPickNumbers: number[];
}

interface LeagueConfig {
  format: "points" | "roto" | "head_to_head";
  rosterPositions: string[];
  teamCount: number;
}
```

```typescript
// packages/extension/src/content-script.ts
import { ESPNAdapter } from "./adapters/espn";
import { YahooAdapter } from "./adapters/yahoo";

function getAdapter(): PlatformAdapter {
  const host = window.location.hostname;
  if (host.includes("espn.com")) return new ESPNAdapter();
  if (host.includes("yahoo.com")) return new YahooAdapter();
  throw new Error(`Unsupported platform: ${host}`);
}
```

---

## 5. ESPN DOM Observer

**ESPN DOM risk:** ESPN can change their draft room UI at any time. Use multiple CSS selector fallbacks and always maintain a test fixture. Always support manual fallback mode.

```typescript
// packages/extension/src/adapters/espn.ts

const PICK_SELECTORS = [
  '[data-testid="draft-pick"]',
  ".pick--completed .playerName",                          // fallback 1
  ".draftPick .playerNameAndInfo .playerName",             // fallback 2
  '[class*="playerName"]',                                 // fallback 3 (broad)
];

class ESPNAdapter implements PlatformAdapter {
  private observer: MutationObserver;
  private pickedPlayerNames = new Set<string>();

  detectPicks(callback: (pick: Pick) => void): void {
    this.observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of Array.from(mutation.addedNodes)) {
          if (node instanceof Element) {
            this.tryExtractPick(node, callback);
          }
        }
      }
    });

    const target = document.querySelector("#draft-board") ?? document.body;
    this.observer.observe(target, { childList: true, subtree: true });
  }

  private tryExtractPick(node: Element, callback: (pick: Pick) => void): void {
    for (const selector of PICK_SELECTORS) {
      const el = node.matches(selector) ? node : node.querySelector(selector);
      if (el) {
        const playerName = el.textContent?.trim();
        const pickNumber = this.extractPickNumber(node);

        if (playerName && !this.pickedPlayerNames.has(playerName)) {
          this.pickedPlayerNames.add(playerName);
          callback({ playerName, pickNumber: pickNumber ?? 0 });
        }
        break;
      }
    }
  }

  private extractPickNumber(node: Element): number | undefined {
    const attr = node.getAttribute("data-pick")
      ?? node.closest("[data-pick]")?.getAttribute("data-pick");
    return attr ? parseInt(attr, 10) : undefined;
  }

  cleanup(): void {
    this.observer.disconnect();
  }
}
```

### Maintaining Test Fixtures

Keep a static HTML snapshot of the ESPN draft room in `__tests__/fixtures/espn-draft-room.html`. Run adapter tests against it with `jsdom`. Update the fixture after any ESPN UI change is detected.

---

## 6. Service Worker (WebSocket Management)

**Critical:** MV3 service workers can be terminated by Chrome when idle. The WebSocket connection must reconnect with exponential backoff and recover session state on reconnect.

```typescript
// packages/extension/src/service-worker.ts

let ws: WebSocket | null = null;
let sessionId: string | null = null;
let wsUrl: string | null = null;
let reconnectDelay = 1000;

// ── Message routing ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  switch (message.type) {
    case "INIT_SESSION":
      sessionId = message.sessionId;
      wsUrl = message.wsUrl;
      connectWebSocket();
      sendResponse({ ok: true });
      break;

    case "PICK_DETECTED":
      ws?.send(JSON.stringify({
        type: "pick",
        player_name: message.playerName,
        pick_number: message.pickNumber,
      }));
      break;

    case "MANUAL_PICK":
      void submitManualPickOverHttp({
        sessionId,
        playerName: message.playerName,
        round: message.round,
        pick: message.pick,
      });
      break;

    case "GET_SUGGESTIONS":
      ws?.send(JSON.stringify({
        type: "get_suggestions",
        position_need: message.positionNeed ?? null,
      }));
      break;
  }
});

// ── WebSocket with exponential backoff ───────────────────────────────────────

function connectWebSocket(): void {
  if (!wsUrl) return;

  chrome.storage.local.get("pucklogic_token", ({ pucklogic_token }) => {
    ws = new WebSocket(`${wsUrl}?token=${pucklogic_token}`);

    ws.onopen = () => {
      reconnectDelay = 1000;  // reset backoff on successful connection
      // Request full state on reconnect (handles service worker restart)
      ws?.send(JSON.stringify({ type: "sync_state", session_id: sessionId }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      chrome.runtime.sendMessage({ type: "WS_MESSAGE", data });
    };

    ws.onclose = () => {
      ws = null;
      setTimeout(() => {
        reconnectDelay = Math.min(reconnectDelay * 2, 30_000);  // max 30s
        connectWebSocket();
      }, reconnectDelay);
    };

    ws.onerror = () => ws?.close();
  });
}
```

### WebSocket Message Protocol

| Direction | Message type | Payload |
|-----------|-------------|---------|
| client → server | `pick` | `{ player_name, pick_number? }` |
| client → server | `sync_state` | `{ session_id }` |
| client → server | `get_suggestions` | `{ position_need? }` |
| server → client | `suggestions` | `{ players: RankedPlayer[] }` |
| server → client | `state_update` | `{ picks: [], available: [] }` |
| server → client | `error` | `{ message }` |

For current `008` / `008c` launch scope, adapter readiness centers on `pick`, `sync_state`, `state_update`, and `error`. Suggestion messages are optional and should not block sync-adapter delivery.

---

## 7. Extension UI Surface

`008c` does **not** establish the final extension popup/sidebar UX. The current implementation scope is the runtime foundation needed for sync adapters:

- attach to supported draft-room pages
- detect picks through platform adapters
- forward sync/recovery/manual-fallback events through the shared protocol
- surface reconnect/degraded/manual-mode state to the extension runtime

Future popup/sidebar UX should be documented here only once those surfaces exist and have an approved implementation contract.

---

## 8. Auth Handoff (Web App → Extension)

The extension never handles payments. The flow is:

1. User purchases draft session on **pucklogic.com** via Stripe Checkout
2. After successful payment, web app creates draft session via `POST /draft-sessions/start`
3. Web app stores `{ session_id, jwt_token }` under the user's account for later resume/attach flows
4. Extension popup detects user is logged in and resumes or inspects the active session through the current draft-session API surface (`/draft-sessions/start`, `/draft-sessions/{session_id}/resume`, `/draft-sessions/{session_id}/sync-state`)
5. Extension stores `pucklogic_token` in `chrome.storage.local`
6. Extension service worker connects: `wss://api.pucklogic.com/draft-sessions/{session_id}/ws?token={jwt_token}`

```typescript
// Popup: authenticate and init session
async function initSession() {
  const token = await getStoredToken();  // from chrome.storage.local
  const res = await fetch(`https://api.pucklogic.com/draft-sessions/${sessionId}/resume`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const { session_id, ws_url } = await res.json();

  chrome.runtime.sendMessage({
    type: "INIT_SESSION",
    sessionId: session_id,
    wsUrl: ws_url,
  });
}
```

---

## 9. Manual Fallback Mode

When DOM detection fails (ESPN UI change), the popup shows a "Mark Pick" button:

Manual picks should converge through `POST /draft-sessions/{session_id}/manual-picks` so they use the same authoritative session model as automatic picks instead of going over the WebSocket directly.

```typescript
function ManualPickButton() {
  const [playerName, setPlayerName] = useState("");

  const submit = () => {
    chrome.runtime.sendMessage({
      type: "MANUAL_PICK",
      playerName,
      round: currentRound,
      pick: currentPick,
    });
    setPlayerName("");
  };

  return (
    <div className="mt-2 border-t pt-2">
      <p className="text-xs text-muted-foreground">Manual pick entry</p>
      <input
        value={playerName}
        onChange={(e) => setPlayerName(e.target.value)}
        placeholder="Player name..."
        className="w-full text-sm border rounded px-2 py-1"
      />
      <button onClick={submit} className="w-full text-sm bg-primary text-white rounded mt-1 py-1">
        Mark Pick
      </button>
    </div>
  );
}
```

---

## 10. Shared Components (packages/ui)

The extension popup and web app share components from `packages/ui`:

| Component | Used by | Purpose |
|-----------|---------|---------|
| `PlayerCard` | Extension popup, web trends panel | Player detail display |
| `RankingsTable` | Web dashboard | Sortable rankings grid |
| `SuggestionPanel` | Extension popup | Best-available list |

Import via Turborepo workspace: `import { PlayerCard } from "@pucklogic/ui"`.

---

## 11. Monetization Flow

- Extension is free to install, requires auth to activate
- $2.99 per draft session — purchased on web app (Chrome Web Store compliance)
- No payment UI in extension
- Draft-session expiry is backend-owned and configurable; the extension must not assume a fixed duration
- A/B test $1.99 vs $3.99 post-launch

---

## 12. Testing Conventions

- **Framework:** Vitest + `@testing-library/react` for popup components
- **DOM adapter tests:** `jsdom` with ESPN/Yahoo draft room HTML fixtures
- **Fixtures:** `__tests__/fixtures/espn-draft-room.html`, `yahoo-draft-room.html`
- **Coverage:** Run `pnpm test` from `packages/extension/`
- **Service worker tests:** Mock `chrome.runtime.*` and `WebSocket` APIs
- TDD required: write failing test before adapter implementation

---

## 13. Key Risks

| Risk | Mitigation |
|------|-----------|
| ESPN/Yahoo DOM changes | 3–5 selector fallbacks per platform, manual fallback mode, HTML test fixtures |
| Service worker terminated by Chrome | WebSocket reconnection with exponential backoff (max 30s), `sync_state` on reconnect |
| Chrome Web Store rejection | Submit 3 weeks early, privacy policy, no payment UI in extension, MV3 compliant |
| Yahoo support (Phase 4) | Same adapter pattern as ESPN, but keep Yahoo gated/non-blocking until manual draft-room verification succeeds |

## Launch scope alignment

- `008c` covers extension sync adapters and recovery behavior, not full extension UX ownership.
- ESPN is launch-critical.
- Yahoo is secondary and gated.
- Manual fallback is required for launch.
- Launch planning assumes a single-instance Fly.io backend with Redis deferred until scale requires it.
- Live draft-room manual verification is season-blocked until draft rooms are available again; track that launch-readiness work in `docs/ROADMAP.md`.
- Backend-owned inactivity-timeout confirmation and broader analytics/metrics planning are tracked as pre-launch follow-ups, not as ad hoc `008c` scope expansion.
