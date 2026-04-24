# PuckLogic — Extension Reference

**Domain:** Chrome MV3 extension (`packages/extension/`)  
**See also:** [pucklogic-architecture.md](pucklogic-architecture.md), [plans/008c-extension-sync-adapters.md](plans/008c-extension-sync-adapters.md)

---

## 1. Scope (current)

This doc reflects the **implemented 008c sync-adapter runtime**, not a future popup/sidebar product UI.

Current extension responsibilities:

- Connect background service worker to draft-session WebSocket
- Forward detected picks from content runtime to the backend session
- Trigger sync recovery (`sync_state`) on connect/reconnect
- Stop reconnect attempts after the backend explicitly denies a terminal closed session
- Emit observability signals for socket lifecycle and fallback behavior
- Detect draft-room context and parse latest picks for ESPN + Yahoo helpers
- Keep Yahoo explicitly launch-gated (non-blocking) pending manual verification

Out of scope in the current code:

- Payment flows
- Extension popup/sidebar UI surface
- Shared `packages/ui` extension components
- Direct manual-pick HTTP submission from extension runtime

---

## 2. Project Structure

```text
packages/extension/
├── manifest.json
├── package.json
├── tsconfig.json
├── vite.config.ts
├── vitest.config.ts
└── src/
    ├── background/
    │   └── index.ts
    ├── content/
    │   ├── espn.ts
    │   ├── yahoo.ts
    │   ├── manualFallback.ts
    │   └── shared.ts
    ├── shared/
    │   └── protocol.ts
    └── __tests__/
        ├── background.test.ts
        ├── espn.test.ts
        ├── yahoo.test.ts
        ├── fallback.test.ts
        ├── protocol.test.ts
        └── manifest.test.ts
```

---

## 3. Manifest Contract (MV3)

`packages/extension/manifest.json` currently ships:

- `name`: `PuckLogic Draft Sync`
- `version`: `0.1.0`
- background service worker: `background.js` (`type: module`)
- permissions: `storage`
- host permissions:
  - `https://api.pucklogic.com/*`
  - `https://fantasy.espn.com/*`
  - `https://sports.yahoo.com/*`
- content script injection:
  - ESPN pages load `espn.js`
  - Yahoo pages load `yahoo.js`

Regression coverage: `src/__tests__/manifest.test.ts` verifies ESPN/Yahoo content script targets.

---

## 4. Build & Packaging

Build command:

- `pnpm --filter @pucklogic/extension build`

`vite.config.ts` defines multi-entry outputs:

- `background` → `src/background/index.ts` → `dist/background.js`
- `espn` → `src/content/espn.ts` → `dist/espn.js`
- `yahoo` → `src/content/yahoo.ts` → `dist/yahoo.js`

A Vite plugin copies `manifest.json` into `dist/manifest.json` after bundle.

---

## 5. Background Session Bridge

`src/background/index.ts` provides `BackgroundSessionBridge` with:

- `initSession({ sessionId, wsUrl })` to establish socket
- optional token attachment in query string (`?token=...`)
- `handleRuntimeMessage` forwarding `PICK_DETECTED` → WS `pick` only when socket is open (`readyState === 1`)
- `sync_state` request on every successful open
- exponential reconnect backoff from 1s up to 30s
- structured backend error handling so `{"type":"error","payload":{"message":"session is closed"}}`
  disables reconnect for terminal sessions instead of retry-looping forever
- observability signals:
  - `socket_attach_success`
  - `socket_attach_failure`
  - `socket_open`
  - `socket_close`
  - `socket_reconnect_attempt`
  - `sync_recovery` (on reconnect after prior successful connection)

---

## 6. Protocol Surface

`src/shared/protocol.ts` declares:

Required client events:

- `pick`
- `sync_state`

Required server events:

- `state_update`
- `error`

Optional events:

- client: `get_suggestions`
- server: `suggestions`

Validators shipped:

- `isSyncStatePayload`
- `isPickPayload`

Observability catalog includes socket lifecycle + fallback/de-sync signals.

---

## 7. Content Helpers & Adapters

### ESPN (`src/content/espn.ts`)

- `detectEspnDraftRoom(url)` checks ESPN host + `draft` path presence
- `extractLatestEspnPick(doc)` parses first matching pick container using selector fallbacks
- signal helpers:
  - `buildEspnReconnectSignal(sessionId)`
  - `buildEspnDegradedStateSignal(reason)`

### Yahoo (`src/content/yahoo.ts`)

- `YAHOO_LAUNCH_POLICY` is hard-coded gated/non-blocking/manual-verification-required
- `detectYahooDraftRoom(url)` accepts draft-room paths (`/draftroom` or `/draft(/|$)`), rejects false positives like `draftresults`
- `extractLatestYahooPick(doc)` parses pick data via selector fallbacks

### Shared parsing (`src/content/shared.ts`)

- `textFromFirstMatch(root, selectors)`
- `parsePickNumber(text)`
- `DetectedPick` type

---

## 8. Manual Fallback Behavior

`src/content/manualFallback.ts` contains pure state/signal helpers:

- `shouldEscalateToManualFallback`
- `buildFallbackSignal`
- `toManualFallbackState`

Current signal behavior:

- reason `selector_failure` → observability `['selector_fallback', 'manual_fallback_activated']`
- reason `sync_confidence_low` → observability `['manual_fallback_activated']` only

This is runtime-state modeling; no popup/manual-entry form is implemented in this package today.

---

## 9. Test Coverage

Run:

- `pnpm --filter @pucklogic/extension test`

Current suite:

- 6 test files
- 32 passing tests

Coverage areas:

- protocol contract + validators
- background bridge forwarding/reconnect/observability
- ESPN parsing + reconnect/degraded signals
- Yahoo parsing + launch-gate policy + URL detection strictness
- fallback escalation + observability tagging
- manifest content-script declarations

---

## 10. Launch Notes / Risks

- ESPN remains launch-critical adapter path.
- Yahoo remains explicitly gated and non-blocking until manual live-room verification is possible.
- DOM volatility risk is mitigated with selector fallbacks + manual fallback state signaling.
- Extension runtime assumes backend draft-session authority (WS primary, recovery via `sync_state`).
- Broader UX/payment/monetization behavior remains web-app/domain scope, not extension runtime scope.
