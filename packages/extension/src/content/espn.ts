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
    container = doc.querySelector(selector);
    if (container) {
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
