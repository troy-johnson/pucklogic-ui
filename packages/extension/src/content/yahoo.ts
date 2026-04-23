import { type DetectedPick, parsePickNumber, textFromFirstMatch } from "./shared";

export const YAHOO_LAUNCH_POLICY = {
  gated: true,
  blocking: false,
  requiresManualVerification: true,
} as const;

const PICK_CONTAINER_SELECTORS = [
  '[data-testid="draft-pick"]',
  ".DraftPick",
  ".draft-pick",
  '[class*="DraftPick"]',
];

const PLAYER_NAME_SELECTORS = [
  ".player-name",
  ".PlayerName",
  ".PlayerInfo .PlayerName",
  '[class*="PlayerName"]',
];

const PICK_NUMBER_SELECTORS = [".pick-number", ".PickNumber", '[class*="PickNumber"]'];

const TEAM_SELECTORS = [".team", ".Team", '[class*="Team"]'];
const POSITION_SELECTORS = [".position", ".Position", '[class*="Position"]'];

export function detectYahooDraftRoom(url: string): boolean {
  const parsed = new URL(url);
  const hostname = parsed.hostname.toLowerCase();
  const path = parsed.pathname.toLowerCase();

  const isDraftRoomPath = path.includes("/draftroom") || /\/draft(\/|$)/.test(path);

  return hostname.includes("yahoo.com") && isDraftRoomPath;
}

export function extractLatestYahooPick(doc: Document): DetectedPick | null {
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

export function startYahooContentScript(
  sendPickMessage: (playerName: string, pickNumber?: number) => void,
  {
    url = window.location.href,
    doc = document,
    onDesync,
  }: { url?: string; doc?: Document; onDesync?: () => void } = {},
): MutationObserver | null {
  if (YAHOO_LAUNCH_POLICY.gated) {
    return null;
  }

  if (!detectYahooDraftRoom(url)) {
    return null;
  }

  let lastPlayerName: string | null = null;
  let lastPickNumber: number | undefined;

  const checkAndSend = () => {
    const pick = extractLatestYahooPick(doc);
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
  startYahooContentScript(
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
