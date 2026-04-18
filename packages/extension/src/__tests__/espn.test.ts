import { describe, expect, it } from "vitest";

import {
  buildEspnDegradedStateSignal,
  buildEspnReconnectSignal,
  detectEspnDraftRoom,
  extractLatestEspnPick,
} from "../content/espn";

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
});
