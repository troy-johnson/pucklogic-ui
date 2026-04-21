import { type DetectedPick, parsePickNumber, textFromFirstMatch } from "./shared";

export type EspnReconnectSignal = {
  type: "sync_state";
  session_id: string;
  source: "espn";
};

export type EspnDegradedStateSignal = {
  type: "error";
  message: string;
  source: "espn";
};

const PICK_CONTAINER_SELECTORS = [
  '[data-testid="draft-pick"]',
  ".pick--completed",
  ".draftPick",
  '[class*="draftPick"]',
];

const PLAYER_NAME_SELECTORS = [
  ".player-name",
  ".playerName",
  ".playerNameAndInfo .playerName",
  '[class*="playerName"]',
];

const PICK_NUMBER_SELECTORS = [".pick-number", ".pick", '[class*="pickNumber"]'];

const TEAM_SELECTORS = [".team", '[class*="team"]'];
const POSITION_SELECTORS = [".position", '[class*="position"]'];

export function detectEspnDraftRoom(url: string): boolean {
  const parsed = new URL(url);
  return parsed.hostname.includes("espn.com") && parsed.pathname.toLowerCase().includes("draft");
}

export function extractLatestEspnPick(doc: Document): DetectedPick | null {
  let container: Element | null = null;

  for (const selector of PICK_CONTAINER_SELECTORS) {
    const all = doc.querySelectorAll(selector);
    if (all.length > 0) {
      container = all[all.length - 1];
      break;
    }
  }

  if (!container) {
    return null;
  }

  const playerName = textFromFirstMatch(container, PLAYER_NAME_SELECTORS);
  if (!playerName) {
    return null;
  }

  const pick: DetectedPick = {
    pickNumber: parsePickNumber(textFromFirstMatch(container, PICK_NUMBER_SELECTORS)),
    playerName,
  };

  const team = textFromFirstMatch(container, TEAM_SELECTORS);
  const position = textFromFirstMatch(container, POSITION_SELECTORS);

  if (team) {
    pick.team = team;
  }

  if (position) {
    pick.position = position;
  }

  return pick;
}

export function buildEspnReconnectSignal(sessionId: string): EspnReconnectSignal {
  return {
    type: "sync_state",
    session_id: sessionId,
    source: "espn",
  };
}

export function buildEspnDegradedStateSignal(reason: string): EspnDegradedStateSignal {
  return {
    type: "error",
    message: `espn_degraded_state:${reason}`,
    source: "espn",
  };
}

export function startEspnContentScript(
  sendPickMessage: (playerName: string, pickNumber?: number) => void,
  {
    url = window.location.href,
    doc = document,
    onDesync,
  }: { url?: string; doc?: Document; onDesync?: () => void } = {},
): MutationObserver | null {
  if (!detectEspnDraftRoom(url)) {
    return null;
  }

  let lastPlayerName: string | null = null;
  let lastPickNumber: number | undefined;

  const checkAndSend = () => {
    const pick = extractLatestEspnPick(doc);
    if (!pick) {
      if (lastPlayerName !== null) {
        onDesync?.();
        lastPlayerName = null;
        lastPickNumber = undefined;
      }
      return;
    }
    if (pick.playerName === lastPlayerName && pick.pickNumber === lastPickNumber) return;
    lastPlayerName = pick.playerName;
    lastPickNumber = pick.pickNumber;
    sendPickMessage(pick.playerName, pick.pickNumber);
  };

  checkAndSend();

  const observer = new MutationObserver(checkAndSend);
  observer.observe(doc.body ?? doc.documentElement, { childList: true, subtree: true });
  return observer;
}

// Top-level content-script entry point — only runs in the actual extension context
if (typeof chrome !== "undefined" && chrome.runtime?.id) {
  startEspnContentScript(
    (playerName, pickNumber) => {
      chrome.runtime.sendMessage({ type: "PICK_DETECTED", playerName, pickNumber });
    },
    {
      onDesync: () => {
        chrome.runtime.sendMessage({ type: "SYNC_DESYNC" });
      },
    },
  );
}
