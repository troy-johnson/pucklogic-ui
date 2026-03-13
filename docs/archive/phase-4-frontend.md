# PuckLogic Phase 4 — Frontend Implementation

## Browser Extension — Chrome MV3 Draft Monitor + Web App Draft Setup

**Timeline:** August – September 2026 (Phase 4)
**Target Release:** v1.0 (September 2026)
**Backend Reference:** `docs/phase-4-backend.md`

---

## Overview

Phase 4 frontend has two parts:

1. **Chrome MV3 Extension** (`packages/extension`) — content script watches the ESPN Fantasy draft room DOM for picks, service worker manages the WebSocket connection to the backend, and a React popup displays best-available suggestions.
2. **Web App Draft Setup** (`apps/web`) — the Stripe payment + session creation flow users complete before their draft begins.

Shared React components from `packages/ui` are used in both the extension popup and the web app draft review page, keeping visual language consistent.

**Deliverables:**
1. ✅ Chrome MV3 manifest (`packages/extension/manifest.json`)
2. ✅ Content script — `MutationObserver` watching ESPN Fantasy draft room DOM
3. ✅ Service worker — WebSocket connection management and message relay
4. ✅ Extension popup — best-available suggestions panel
5. ✅ Web app draft setup page (`/dashboard/draft/new`) — Stripe Payment Element + session creation
6. ✅ Shared React components from `packages/ui` (PlayerCard, SuggestionsList)
7. ✅ Test coverage (Vitest for extension logic, React Testing Library for popup + web)

---

## 1. Chrome MV3 Extension

### 1.1 Manifest

**Location:** `packages/extension/manifest.json`

```json
{
  "manifest_version": 3,
  "name": "PuckLogic Draft Monitor",
  "version": "1.0.0",
  "description": "Real-time best-available suggestions for your fantasy hockey draft",
  "permissions": ["storage", "tabs"],
  "host_permissions": ["https://*.espn.com/*"],
  "background": {
    "service_worker": "service-worker.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://fantasy.espn.com/*/draft*"],
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

**Security:** No `eval`, no `unsafe-inline`. All code must comply with MV3 CSP restrictions. The `type: "module"` on the service worker enables ES module imports.

### 1.2 Build Configuration

**Location:** `packages/extension/vite.config.ts`

Vite bundles three separate entry points: `content-script.ts`, `service-worker.ts`, and `popup/popup.tsx`. Each outputs a self-contained JS file. The `popup.html` is copied as-is.

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        "content-script": "src/content-script.ts",
        "service-worker": "src/service-worker.ts",
        popup: "src/popup/popup.html",
      },
      output: {
        entryFileNames: "[name].js",
        format: "es",
      },
    },
    outDir: "dist",
    emptyOutDir: true,
  },
});
```

---

## 2. Content Script — ESPN DOM Observer

**Location:** `packages/extension/src/content-script.ts`

**ESPN DOM risk:** ESPN can change their draft room UI at any time. Multiple CSS selector fallbacks are essential. Always maintain a test fixture of the draft room HTML. The extension must also support a **manual pick entry** fallback mode.

### 2.1 Observer Implementation

```typescript
const PICK_SELECTORS = [
  '[data-testid="draft-pick"]',
  ".pick--completed .playerName",                          // fallback 1
  ".draftPick .playerNameAndInfo .playerName",             // fallback 2
  '[class*="playerName"]',                                 // fallback 3 (broad)
];

class EspnDraftObserver {
  private observer: MutationObserver;
  private pickedPlayerNames = new Set<string>();

  start(): void {
    this.observer = new MutationObserver((mutations) => {
      this.handleMutations(mutations);
    });

    // Prefer the draft board container; fall back to body
    const target = document.querySelector("#draft-board") ?? document.body;
    this.observer.observe(target, { childList: true, subtree: true });
  }

  private handleMutations(mutations: MutationRecord[]): void {
    for (const mutation of mutations) {
      for (const node of Array.from(mutation.addedNodes)) {
        if (node instanceof Element) {
          this.tryExtractPick(node);
        }
      }
    }
  }

  private tryExtractPick(node: Element): void {
    for (const selector of PICK_SELECTORS) {
      const el = node.matches(selector)
        ? node
        : node.querySelector(selector);

      if (el) {
        const playerName = el.textContent?.trim();
        const pickNumber = this.extractPickNumber(node);

        if (playerName && !this.pickedPlayerNames.has(playerName)) {
          this.pickedPlayerNames.add(playerName);
          chrome.runtime.sendMessage({
            type: "PICK_DETECTED",
            playerName,
            pickNumber,
          });
        }
        break;
      }
    }
  }

  private extractPickNumber(node: Element): number | undefined {
    // Tries multiple attributes / text patterns
    const pickAttr = node.getAttribute("data-pick") ?? node.closest("[data-pick]")?.getAttribute("data-pick");
    return pickAttr ? parseInt(pickAttr, 10) : undefined;
  }

  stop(): void {
    this.observer.disconnect();
  }
}

const draftObserver = new EspnDraftObserver();
draftObserver.start();

// Listen for stop command from service worker
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "STOP_OBSERVER") {
    draftObserver.stop();
  }
});
```

---

## 3. Service Worker

**Location:** `packages/extension/src/service-worker.ts`

The service worker manages the WebSocket lifecycle and relays messages between the content script, the popup, and the backend.

```typescript
let ws: WebSocket | null = null;
let sessionId: string | null = null;
let wsUrl: string | null = null;
let reconnectDelay = 1000;

// ── Message handling from content script and popup ──────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "INIT_SESSION") {
    sessionId = message.sessionId;
    wsUrl = message.wsUrl;
    connectWebSocket();
    sendResponse({ ok: true });
  }

  if (message.type === "PICK_DETECTED") {
    ws?.send(
      JSON.stringify({
        type: "pick",
        player_name: message.playerName,
        pick_number: message.pickNumber,
      })
    );
  }

  if (message.type === "GET_SUGGESTIONS") {
    ws?.send(
      JSON.stringify({
        type: "get_suggestions",
        position_need: message.positionNeed ?? null,
      })
    );
  }

  if (message.type === "MANUAL_PICK") {
    ws?.send(
      JSON.stringify({
        type: "pick",
        player_name: message.playerName,
        round: message.round,
        pick: message.pick,
      })
    );
  }
});

// ── WebSocket connection ─────────────────────────────────────────────────────

function connectWebSocket(): void {
  if (!wsUrl) return;

  // Append JWT token for auth
  chrome.storage.local.get("pucklogic_token", ({ pucklogic_token }) => {
    ws = new WebSocket(`${wsUrl}?token=${pucklogic_token}`);

    ws.onopen = () => {
      reconnectDelay = 1000; // reset backoff
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      // Broadcast to popup
      chrome.runtime.sendMessage({ type: "WS_MESSAGE", data });
    };

    ws.onclose = () => {
      ws = null;
      // Exponential backoff reconnect (max 30s)
      setTimeout(() => {
        reconnectDelay = Math.min(reconnectDelay * 2, 30_000);
        connectWebSocket();
      }, reconnectDelay);
    };

    ws.onerror = () => {
      ws?.close();
    };
  });
}
```

---

## 4. Extension Popup

**Location:** `packages/extension/src/popup/`

### 4.1 File Structure

```
popup/
  App.tsx                    # Root popup component — state management
  components/
    SuggestionsList.tsx      # Top 10 best-available cards
    PlayerCard.tsx           # Name, position, team, fantasy_pts, VORP, badges
    PositionFilter.tsx       # C / LW / RW / D / G filter chips
    ManualPickEntry.tsx      # Fallback: type a player name to record a pick
    ConnectionStatus.tsx     # WS connected / disconnected indicator
  popup.html                 # HTML shell (loads popup.js)
  popup.tsx                  # React root render
```

### 4.2 App Component

```tsx
// packages/extension/src/popup/App.tsx
"use client";

import { useEffect, useState } from "react";
import { SuggestionsList } from "./components/SuggestionsList";
import { PositionFilter } from "./components/PositionFilter";
import { ManualPickEntry } from "./components/ManualPickEntry";
import { ConnectionStatus } from "./components/ConnectionStatus";
import type { BestAvailablePlayer } from "@pucklogic/ui";

export default function App() {
  const [suggestions, setSuggestions] = useState<BestAvailablePlayer[]>([]);
  const [positionFilter, setPositionFilter] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // Listen for WebSocket messages relayed from service worker
    chrome.runtime.onMessage.addListener((message) => {
      if (message.type === "WS_MESSAGE") {
        const { data } = message;
        if (data.type === "suggestions") {
          setSuggestions(data.players);
        }
        if (data.type === "session_state") {
          setConnected(true);
        }
        if (data.type === "error") {
          console.error("Draft WS error:", data.message);
        }
      }
    });

    // Request initial suggestions on open
    chrome.runtime.sendMessage({ type: "GET_SUGGESTIONS" });
  }, []);

  function handlePositionFilter(pos: string | null) {
    setPositionFilter(pos);
    chrome.runtime.sendMessage({ type: "GET_SUGGESTIONS", positionNeed: pos });
  }

  return (
    <div className="w-80 min-h-96 bg-background p-3 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">PuckLogic Draft Monitor</span>
        <ConnectionStatus connected={connected} />
      </div>
      <PositionFilter active={positionFilter} onChange={handlePositionFilter} />
      <SuggestionsList players={suggestions} />
      <ManualPickEntry />
    </div>
  );
}
```

### 4.3 SuggestionsList Component

```tsx
// packages/extension/src/popup/components/SuggestionsList.tsx
import { PlayerCard } from "@pucklogic/ui";
import type { BestAvailablePlayer } from "@pucklogic/ui";

interface SuggestionsListProps {
  players: BestAvailablePlayer[];
}

export function SuggestionsList({ players }: SuggestionsListProps) {
  if (players.length === 0) {
    return <p className="text-muted-foreground text-xs text-center py-4">Waiting for draft data…</p>;
  }

  return (
    <div className="flex flex-col gap-1.5">
      {players.map((player, idx) => (
        <PlayerCard key={player.player_id} player={player} rank={idx + 1} />
      ))}
    </div>
  );
}
```

### 4.4 ManualPickEntry (Fallback Mode)

```tsx
// packages/extension/src/popup/components/ManualPickEntry.tsx
import { useState } from "react";

export function ManualPickEntry() {
  const [name, setName] = useState("");

  function submitPick() {
    if (!name.trim()) return;
    chrome.runtime.sendMessage({ type: "MANUAL_PICK", playerName: name.trim() });
    setName("");
  }

  return (
    <div className="flex gap-1.5 border-t pt-2">
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submitPick()}
        placeholder="Enter picked player…"
        className="flex-1 text-xs rounded border px-2 py-1"
      />
      <button
        onClick={submitPick}
        className="text-xs rounded border px-2 py-1 hover:bg-accent"
      >
        Pick
      </button>
    </div>
  );
}
```

---

## 5. Shared `packages/ui` Components

**Location:** `packages/ui/src/`

`PlayerCard` is defined here and imported by both the extension popup and the web app's draft review page.

```tsx
// packages/ui/src/PlayerCard.tsx
export interface BestAvailablePlayer {
  player_id: string;
  name: string;
  team: string;
  position: string;
  fantasy_pts: number;
  vorp: number;
  breakout_score?: number;  // null before Phase 3
}

interface PlayerCardProps {
  player: BestAvailablePlayer;
  rank: number;
}

export function PlayerCard({ player, rank }: PlayerCardProps) {
  const vorpColor = player.vorp >= 0 ? "text-green-500" : "text-red-500";

  return (
    <div className="flex items-center gap-2 rounded-md border px-2.5 py-2 text-xs">
      <span className="w-5 text-muted-foreground font-mono">{rank}</span>
      <div className="flex-1">
        <p className="font-medium">{player.name}</p>
        <p className="text-muted-foreground">{player.team} · {player.position}</p>
      </div>
      <div className="text-right">
        <p className="font-mono font-medium">{player.fantasy_pts.toFixed(1)} pts</p>
        <p className={`font-mono text-[10px] ${vorpColor}`}>
          VORP {player.vorp >= 0 ? "+" : ""}{player.vorp.toFixed(1)}
        </p>
      </div>
      {player.breakout_score !== undefined && player.breakout_score > 0.65 && (
        <span className="rounded bg-green-100 px-1 py-0.5 text-[10px] font-medium text-green-700">
          ↑ Breakout
        </span>
      )}
    </div>
  );
}
```

---

## 6. Web App — Draft Setup Page

**Location:** `apps/web/src/app/(dashboard)/draft/new/page.tsx`

### 6.1 Flow

1. User selects league config (rounds, teams, format, scoring preset)
2. Stripe Payment Element embedded — one-time $2.99 payment
3. On payment success → `POST /api/draft/create-session` → receive `session_id` + `ws_url`
4. Session credentials stored in `chrome.storage.local` via `window.postMessage` (picked up by a content script running on the page, which then calls `chrome.storage.local.set`)
5. Show "Open ESPN Draft Room" CTA with activation instructions

### 6.2 Implementation

```tsx
"use client";

import { useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js";

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

type Step = "config" | "payment" | "ready";

export default function NewDraftPage() {
  const [step, setStep] = useState<Step>("config");
  const [leagueConfig, setLeagueConfig] = useState<LeagueConfig>(DEFAULT_CONFIG);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  async function handleConfigSubmit() {
    // Create Stripe PaymentIntent on the server
    const res = await fetch("/api/stripe/create-draft-payment-intent", {
      method: "POST",
      body: JSON.stringify({ league_config: leagueConfig }),
    });
    const { client_secret } = await res.json();
    setClientSecret(client_secret);
    setStep("payment");
  }

  async function handlePaymentSuccess(paymentIntentId: string) {
    const res = await fetch("/api/draft/create-session", {
      method: "POST",
      body: JSON.stringify({
        payment_intent_id: paymentIntentId,
        league_config: leagueConfig,
      }),
    });
    const { session_id, ws_url } = await res.json();
    setSessionId(session_id);

    // Tell the extension about the session via postMessage
    // (A companion content script on pucklogic.com picks this up and writes to chrome.storage)
    window.postMessage({ type: "PUCKLOGIC_SESSION", session_id, ws_url }, window.origin);
    setStep("ready");
  }

  if (step === "config") {
    return <LeagueConfigForm config={leagueConfig} onChange={setLeagueConfig} onSubmit={handleConfigSubmit} />;
  }

  if (step === "payment" && clientSecret) {
    return (
      <Elements stripe={stripePromise} options={{ clientSecret }}>
        <DraftPaymentForm onSuccess={handlePaymentSuccess} />
      </Elements>
    );
  }

  return <DraftReadyScreen sessionId={sessionId!} />;
}
```

### 6.3 DraftReadyScreen

Displayed after successful payment and session creation:

```tsx
function DraftReadyScreen({ sessionId }: { sessionId: string }) {
  return (
    <div className="max-w-md mx-auto text-center space-y-4 py-12">
      <div className="text-4xl">🏒</div>
      <h2 className="text-xl font-semibold">Draft session ready!</h2>
      <p className="text-muted-foreground text-sm">
        Open your ESPN Fantasy draft room. The PuckLogic extension will activate automatically.
      </p>
      <p className="font-mono text-xs text-muted-foreground">Session: {sessionId.slice(0, 8)}…</p>
      <a
        href="https://fantasy.espn.com"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
      >
        Open ESPN Draft Room →
      </a>
    </div>
  );
}
```

---

## 7. Testing

### 7.1 Extension Tests

```typescript
// packages/extension/src/__tests__/observer.test.ts

import { JSDOM } from "jsdom";

vi.mock("chrome", () => ({
  runtime: { sendMessage: vi.fn() },
}));

test("detects pick via primary selector and sends message", () => {
  const dom = new JSDOM(`
    <div id="draft-board">
      <div data-testid="draft-pick">Connor McDavid</div>
    </div>
  `);
  // Set up observer against fixture DOM
  // Trigger mutation — add a new pick node
  // Assert chrome.runtime.sendMessage called with { type: 'PICK_DETECTED', playerName: 'Connor McDavid' }
});

test("falls back to secondary selector when primary missing", () => {
  const dom = new JSDOM(`
    <div class="pick--completed"><span class="playerName">Auston Matthews</span></div>
  `);
  // Trigger mutation
  // Assert chrome.runtime.sendMessage called with correct playerName
});

test("does not send duplicate picks for same player", () => {
  // Send the same player twice
  // Assert sendMessage called only once
});


// packages/extension/src/__tests__/service-worker.test.ts

vi.mock("chrome", () => ({
  runtime: { onMessage: { addListener: vi.fn() }, sendMessage: vi.fn() },
  storage: { local: { get: vi.fn((_, cb) => cb({ pucklogic_token: "jwt" })) } },
}));

test("INIT_SESSION triggers WebSocket connection", async () => {
  // Simulate receiving INIT_SESSION message
  // Assert WebSocket was constructed with correct wss:// URL
});

test("PICK_DETECTED relays to WebSocket as pick message", async () => {
  // Simulate open WS, then PICK_DETECTED message
  // Assert ws.send called with { type: 'pick', player_name: '...' }
});

test("WebSocket reconnects with exponential backoff on close", async () => {
  vi.useFakeTimers();
  // Simulate WS close
  // Assert setTimeout called with reconnectDelay
});
```

### 7.2 Popup Tests

```tsx
// packages/extension/src/popup/__tests__/SuggestionsList.test.tsx

import { render, screen } from "@testing-library/react";
import { SuggestionsList } from "../components/SuggestionsList";

const MOCK_PLAYERS = [
  { player_id: "p1", name: "Connor McDavid", team: "EDM", position: "C", fantasy_pts: 85.2, vorp: 42.1 },
  { player_id: "p2", name: "Nathan MacKinnon", team: "COL", position: "C", fantasy_pts: 83.7, vorp: 40.5 },
];

test("renders player cards in order", () => {
  render(<SuggestionsList players={MOCK_PLAYERS} />);
  const names = screen.getAllByRole("paragraph", { name: /./i });
  expect(names[0]).toHaveTextContent("Connor McDavid");
});

test("shows waiting message when no players", () => {
  render(<SuggestionsList players={[]} />);
  expect(screen.getByText(/Waiting for draft data/i)).toBeInTheDocument();
});

test("position filter changes displayed list", async () => {
  // Render App with mocked chrome.runtime, simulate GET_SUGGESTIONS with positionNeed='D'
  // Assert only D players shown after filter click
});
```

### 7.3 Web App Tests

```tsx
// apps/web/src/app/(dashboard)/draft/new/__tests__/page.test.tsx

vi.mock("@stripe/react-stripe-js", () => ({
  Elements: ({ children }: any) => children,
  PaymentElement: () => <div>Payment Form</div>,
  useStripe: () => ({ confirmPayment: vi.fn().mockResolvedValue({ paymentIntent: { id: "pi_x" } }) }),
  useElements: () => ({}),
}));

test("renders config form on mount", () => {
  render(<NewDraftPage />);
  expect(screen.getByText(/League Config/i)).toBeInTheDocument();
});

test("moves to payment step after config submit", async () => {
  // Fill config, submit, assert Stripe Elements rendered
});

test("calls create-session API after payment and moves to ready step", async () => {
  // Mock fetch for both endpoints, complete payment, assert session ID shown
});
```

---

## Appendix: Key Files

```
packages/extension/
  manifest.json
  src/
    content-script.ts              # MutationObserver ESPN pick detection
    service-worker.ts              # WebSocket management + message relay
    popup/
      App.tsx                      # Root popup — state + chrome.runtime listener
      components/
        SuggestionsList.tsx
        PlayerCard.tsx             # Uses shared @pucklogic/ui PlayerCard
        PositionFilter.tsx
        ManualPickEntry.tsx        # Fallback pick entry
        ConnectionStatus.tsx
      popup.html
      popup.tsx                    # React.createRoot render
    __tests__/
      observer.test.ts
      service-worker.test.ts
      popup/
        SuggestionsList.test.tsx
  package.json
  vite.config.ts                   # Multi-entry bundle

packages/ui/
  src/
    PlayerCard.tsx                 # Shared card (extension popup + web)
    index.ts                       # Re-exports

apps/web/
  src/
    app/
      (dashboard)/
        draft/
          new/
            page.tsx               # Stripe payment + session creation
            __tests__/page.test.tsx
    api/
      stripe/
        create-draft-payment-intent/
          route.ts                 # Next.js Route Handler — creates PaymentIntent
```

### ESPN DOM Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| ESPN changes CSS class names | Four layered CSS selector fallbacks |
| ESPN changes DOM structure | `subtree: true` observer catches deep mutations |
| Observer misses a pick | Manual pick entry (`ManualPickEntry`) as guaranteed fallback |
| ESPN requires JavaScript rendering | Content script runs at `document_idle` (after JS renders) |
| Extension update breaks live draft | Test fixtures of ESPN draft room HTML in `__tests__/fixtures/` |

### Extension Monetization Note

The $2–3 draft session payment is completed on the **PuckLogic web app**, not in the extension. This avoids Chrome Web Store payment compliance requirements. The extension activates only after receiving a valid `session_id` from the web app.
