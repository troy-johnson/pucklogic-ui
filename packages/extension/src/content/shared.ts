export type DetectedPick = {
  pickNumber: number;
  playerName: string;
  team?: string;
  position?: string;
};

export function textFromFirstMatch(root: ParentNode, selectors: string[]): string | null {
  for (const selector of selectors) {
    const el = root.querySelector(selector);
    const text = el?.textContent?.trim();

    if (text) {
      return text;
    }
  }

  return null;
}

export function parsePickNumber(text: string | null): number {
  if (!text) {
    return 0;
  }

  const match = text.match(/\d+/);
  if (!match) {
    return 0;
  }

  return Number.parseInt(match[0], 10);
}
