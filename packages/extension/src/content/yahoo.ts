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
