import { describe, expect, it } from "vitest";

import {
  YAHOO_LAUNCH_POLICY,
  detectYahooDraftRoom,
  extractLatestYahooPick,
  startYahooContentScript,
} from "../content/yahoo";

describe("Yahoo adapter", () => {
  it("detects Yahoo draft-room context from hostname and path", () => {
    expect(detectYahooDraftRoom("https://sports.yahoo.com/fantasy/hockey/draftroom/league-1")).toBe(true);
    expect(detectYahooDraftRoom("https://basketball.fantasysports.yahoo.com/hockey/123/draftresults")).toBe(false);
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

  it("extracts the last pick when multiple picks are present", () => {
    const doc = new DOMParser().parseFromString(
      `
      <div>
        <div data-testid="draft-pick"><span class="player-name">Wayne Gretzky</span><span class="pick-number">1</span></div>
        <div data-testid="draft-pick"><span class="player-name">Mario Lemieux</span><span class="pick-number">2</span></div>
        <div data-testid="draft-pick">
          <span class="PickNumber">3</span>
          <span class="PlayerName">Gordie Howe</span>
        </div>
      </div>
      `,
      "text/html",
    );

    expect(extractLatestYahooPick(doc)).toMatchObject({ playerName: "Gordie Howe", pickNumber: 3 });
  });

  it("startYahooContentScript: returns null and sends nothing while policy is gated", () => {
    const sent: string[] = [];
    const doc = new DOMParser().parseFromString(
      `<div><div data-testid="draft-pick"><span class="player-name">Nathan MacKinnon</span></div></div>`,
      "text/html",
    );

    const result = startYahooContentScript((playerName) => sent.push(playerName), {
      url: "https://sports.yahoo.com/fantasy/hockey/draftroom/league-1",
      doc,
    });

    expect(result).toBeNull();
    expect(sent).toHaveLength(0);
  });

  it("remains explicitly gated for launch by policy", () => {
    expect(YAHOO_LAUNCH_POLICY).toEqual({
      gated: true,
      blocking: false,
      requiresManualVerification: true,
    });
  });

  it("extractLatestYahooPick: omits pickNumber when pick-number element is absent", () => {
    const doc = new DOMParser().parseFromString(
      `<div><div data-testid="draft-pick"><span class="player-name">Miro Heiskanen</span></div></div>`,
      "text/html",
    );

    const pick = extractLatestYahooPick(doc);

    expect(pick).not.toBeNull();
    expect(pick!.playerName).toBe("Miro Heiskanen");
    expect(pick!.pickNumber).toBeUndefined();
  });
});
