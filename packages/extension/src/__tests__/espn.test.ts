import { describe, expect, it } from "vitest";

import {
  buildEspnDegradedStateSignal,
  buildEspnReconnectSignal,
  detectEspnDraftRoom,
  extractLatestEspnPick,
  startEspnContentScript,
} from "../content/espn";
import { parsePickNumber } from "../content/shared";

describe("ESPN adapter", () => {
  it("detects ESPN draft-room context from hostname and path", () => {
    expect(detectEspnDraftRoom("https://fantasy.espn.com/hockey/draft?leagueId=1")).toBe(true);
    expect(detectEspnDraftRoom("https://sports.yahoo.com/fantasy/hockey/draftroom")).toBe(false);
    expect(detectEspnDraftRoom("https://fantasy.espn.com/hockey/team?leagueId=1")).toBe(false);
  });

  it("extracts latest pick from primary selector", () => {
    const doc = new DOMParser().parseFromString(
      `
      <div>
        <div data-testid="draft-pick">
          <span class="pick-number">12</span>
          <span class="player-name">Nathan MacKinnon</span>
          <span class="team">COL</span>
          <span class="position">C</span>
        </div>
      </div>
      `,
      "text/html",
    );

    expect(extractLatestEspnPick(doc)).toEqual({
      pickNumber: 12,
      playerName: "Nathan MacKinnon",
      team: "COL",
      position: "C",
    });
  });

  it("extracts latest pick from fallback selector", () => {
    const doc = new DOMParser().parseFromString(
      `
      <div>
        <div class="draftPick">
          <div class="playerNameAndInfo">
            <span class="playerName">Connor Bedard</span>
          </div>
          <span class="pick">7</span>
        </div>
      </div>
      `,
      "text/html",
    );

    expect(extractLatestEspnPick(doc)).toEqual({
      pickNumber: 7,
      playerName: "Connor Bedard",
    });
  });

  it("returns null when no supported pick selectors are present", () => {
    const doc = new DOMParser().parseFromString("<div><p>No pick here</p></div>", "text/html");

    expect(extractLatestEspnPick(doc)).toBeNull();
  });

  it("extracts the last pick when multiple picks are present", () => {
    const doc = new DOMParser().parseFromString(
      `
      <div>
        <div data-testid="draft-pick"><span class="player-name">Wayne Gretzky</span><span class="pick-number">1</span></div>
        <div data-testid="draft-pick"><span class="player-name">Mario Lemieux</span><span class="pick-number">2</span></div>
        <div data-testid="draft-pick">
          <span class="pick-number">3</span>
          <span class="player-name">Gordie Howe</span>
        </div>
      </div>
      `,
      "text/html",
    );

    expect(extractLatestEspnPick(doc)).toMatchObject({ playerName: "Gordie Howe", pickNumber: 3 });
  });

  it("startEspnContentScript: sends pick on startup when draft board has a pick", () => {
    const sent: Array<{ playerName: string; pickNumber?: number }> = [];
    const doc = new DOMParser().parseFromString(
      `<div><div data-testid="draft-pick"><span class="player-name">Connor McDavid</span><span class="pick-number">1</span></div></div>`,
      "text/html",
    );

    const observer = startEspnContentScript(
      (playerName, pickNumber) => sent.push({ playerName, pickNumber }),
      { url: "https://fantasy.espn.com/hockey/draft?leagueId=1", doc },
    );

    expect(sent).toHaveLength(1);
    expect(sent[0]).toEqual({ playerName: "Connor McDavid", pickNumber: 1 });
    observer?.disconnect();
  });

  it("startEspnContentScript: calls onDesync when previously-seen pick disappears from DOM", async () => {
    const doc = new DOMParser().parseFromString(
      `<div id="board"><div data-testid="draft-pick"><span class="player-name">Connor McDavid</span><span class="pick-number">1</span></div></div>`,
      "text/html",
    );

    const desyncs: number[] = [];
    const observer = startEspnContentScript(
      () => {},
      {
        url: "https://fantasy.espn.com/hockey/draft?leagueId=1",
        doc,
        onDesync: () => desyncs.push(1),
      },
    );

    doc.getElementById("board")!.innerHTML = "";
    await Promise.resolve(); // flush MutationObserver microtask

    expect(desyncs).toHaveLength(1);
    observer?.disconnect();
  });

  it("startEspnContentScript: does not repeat onDesync while DOM remains empty", async () => {
    const doc = new DOMParser().parseFromString(
      `<div id="board"><div data-testid="draft-pick"><span class="player-name">Connor McDavid</span><span class="pick-number">1</span></div></div>`,
      "text/html",
    );

    const desyncs: number[] = [];
    const observer = startEspnContentScript(
      () => {},
      {
        url: "https://fantasy.espn.com/hockey/draft?leagueId=1",
        doc,
        onDesync: () => desyncs.push(1),
      },
    );

    const board = doc.getElementById("board")!;
    board.innerHTML = "";
    await Promise.resolve();

    // Second mutation while DOM is still empty — should not re-fire onDesync
    board.setAttribute("data-mutated", "true");
    await Promise.resolve();

    expect(desyncs).toHaveLength(1);
    observer?.disconnect();
  });

  it("startEspnContentScript: returns null for non-ESPN URLs", () => {
    const sent: string[] = [];
    const result = startEspnContentScript((playerName) => sent.push(playerName), {
      url: "https://sports.yahoo.com/fantasy/hockey/draftroom",
    });

    expect(result).toBeNull();
    expect(sent).toHaveLength(0);
  });

  it("reconnect: builds sync_state recovery signal", () => {
    expect(buildEspnReconnectSignal("session-123")).toEqual({
      type: "sync_state",
      session_id: "session-123",
      source: "espn",
    });
  });

  it("reconnect: builds degraded-state error signal when parsing fails", () => {
    expect(buildEspnDegradedStateSignal("selector_miss")).toEqual({
      type: "error",
      message: "espn_degraded_state:selector_miss",
      source: "espn",
    });
  });

  describe("parsePickNumber", () => {
    it("returns undefined for null input", () => {
      expect(parsePickNumber(null)).toBeUndefined();
    });

    it("returns undefined for empty string", () => {
      expect(parsePickNumber("")).toBeUndefined();
    });

    it("returns undefined when text contains no digit sequence", () => {
      expect(parsePickNumber("no digits here")).toBeUndefined();
    });

    it("returns the parsed number for valid pick text", () => {
      expect(parsePickNumber("Pick 7")).toBe(7);
    });

    it("returns the first digit sequence found", () => {
      expect(parsePickNumber("12")).toBe(12);
    });
  });

  it("startEspnContentScript: omits pickNumber when pick-number element is absent", () => {
    const sent: Array<{ playerName: string; pickNumber?: number }> = [];
    const doc = new DOMParser().parseFromString(
      `<div><div data-testid="draft-pick"><span class="player-name">Connor McDavid</span></div></div>`,
      "text/html",
    );

    const observer = startEspnContentScript(
      (playerName, pickNumber) => sent.push({ playerName, pickNumber }),
      { url: "https://fantasy.espn.com/hockey/draft?leagueId=1", doc },
    );

    expect(sent).toHaveLength(1);
    expect(sent[0].playerName).toBe("Connor McDavid");
    expect(sent[0].pickNumber).toBeUndefined();
    observer?.disconnect();
  });
});
