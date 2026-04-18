import { describe, expect, it } from "vitest";

import {
  YAHOO_LAUNCH_POLICY,
  detectYahooDraftRoom,
  extractLatestYahooPick,
} from "../content/yahoo";

describe("Yahoo adapter", () => {
  it("detects Yahoo draft-room context from hostname and path", () => {
    expect(detectYahooDraftRoom("https://sports.yahoo.com/fantasy/hockey/draftroom/league-1")).toBe(true);
    expect(detectYahooDraftRoom("https://basketball.fantasysports.yahoo.com/hockey/123/draftresults")).toBe(true);
    expect(detectYahooDraftRoom("https://fantasy.espn.com/hockey/draft?leagueId=1")).toBe(false);
    expect(detectYahooDraftRoom("https://sports.yahoo.com/fantasy/hockey/league/1")).toBe(false);
  });

  it("extracts latest pick from primary selector", () => {
    const doc = new DOMParser().parseFromString(
      `
      <div>
        <div data-testid="draft-pick">
          <span class="pick-number">22</span>
          <span class="player-name">Miro Heiskanen</span>
          <span class="team">DAL</span>
          <span class="position">D</span>
        </div>
      </div>
      `,
      "text/html",
    );

    expect(extractLatestYahooPick(doc)).toEqual({
      pickNumber: 22,
      playerName: "Miro Heiskanen",
      team: "DAL",
      position: "D",
    });
  });

  it("extracts latest pick from fallback selector", () => {
    const doc = new DOMParser().parseFromString(
      `
      <div>
        <div class="DraftPick">
          <div class="PlayerInfo">
            <span class="PlayerName">Jack Hughes</span>
          </div>
          <span class="PickNumber">13</span>
        </div>
      </div>
      `,
      "text/html",
    );

    expect(extractLatestYahooPick(doc)).toEqual({
      pickNumber: 13,
      playerName: "Jack Hughes",
    });
  });

  it("returns null when no supported selectors are present", () => {
    const doc = new DOMParser().parseFromString("<div><p>No draft pick here</p></div>", "text/html");
    expect(extractLatestYahooPick(doc)).toBeNull();
  });

  it("remains explicitly gated for launch by policy", () => {
    expect(YAHOO_LAUNCH_POLICY).toEqual({
      gated: true,
      blocking: false,
      requiresManualVerification: true,
    });
  });
});
