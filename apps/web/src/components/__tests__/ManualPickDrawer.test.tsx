import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ManualPickDrawer } from "../ManualPickDrawer";
import type { RankedPlayer } from "@/types";

const NULL_STATS = {
  g: null, a: null, plus_minus: null, pim: null, ppg: null, ppa: null,
  ppp: null, shg: null, sha: null, shp: null, sog: null, fow: null,
  fol: null, hits: null, blocks: null, gp: null, gs: null, w: null,
  l: null, ga: null, sa: null, sv: null, sv_pct: null, so: null, otl: null,
};

const PLAYERS: RankedPlayer[] = [
  {
    composite_rank: 1,
    player_id: "p1",
    name: "Connor McDavid",
    team: "EDM",
    default_position: "C",
    platform_positions: [],
    projected_fantasy_points: 30.5,
    vorp: null,
    schedule_score: null,
    off_night_games: null,
    source_count: 1,
    projected_stats: NULL_STATS,
    breakout_score: null,
    regression_risk: null,
  },
  {
    composite_rank: 2,
    player_id: "p2",
    name: "Nathan MacKinnon",
    team: "COL",
    default_position: "C",
    platform_positions: [],
    projected_fantasy_points: 28.0,
    vorp: null,
    schedule_score: null,
    off_night_games: null,
    source_count: 1,
    projected_stats: NULL_STATS,
    breakout_score: null,
    regression_risk: null,
  },
];

describe("ManualPickDrawer", () => {
  it("renders the player search input", () => {
    render(
      <ManualPickDrawer
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        players={PLAYERS}
        currentRound={1}
        currentPick={1}
      />,
    );
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
  });

  it("confirm button is disabled when no player is selected", () => {
    render(
      <ManualPickDrawer
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        players={PLAYERS}
        currentRound={1}
        currentPick={1}
      />,
    );
    expect(screen.getByRole("button", { name: /confirm pick/i })).toBeDisabled();
  });

  it("confirm button is enabled after selecting a player", async () => {
    const user = userEvent.setup();
    render(
      <ManualPickDrawer
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        players={PLAYERS}
        currentRound={1}
        currentPick={1}
      />,
    );
    await user.click(screen.getByText("Connor McDavid"));
    expect(screen.getByRole("button", { name: /confirm pick/i })).not.toBeDisabled();
  });

  it("resets round/pick defaults when reopened with new props", () => {
    const { rerender } = render(
      <ManualPickDrawer
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        players={PLAYERS}
        currentRound={1}
        currentPick={1}
      />,
    );
    expect((screen.getByLabelText(/round/i) as HTMLInputElement).value).toBe("1");

    // Close, advance the draft, then reopen with new round/pick values.
    rerender(
      <ManualPickDrawer
        open={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        players={PLAYERS}
        currentRound={3}
        currentPick={5}
      />,
    );
    rerender(
      <ManualPickDrawer
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        players={PLAYERS}
        currentRound={3}
        currentPick={5}
      />,
    );
    expect((screen.getByLabelText(/round/i) as HTMLInputElement).value).toBe("3");
    expect((screen.getByLabelText(/^pick$/i) as HTMLInputElement).value).toBe("5");
  });

  it('calls onConfirm and shows "Recorded" flash after confirm', async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(
      <ManualPickDrawer
        open
        onClose={vi.fn()}
        onConfirm={onConfirm}
        players={PLAYERS}
        currentRound={1}
        currentPick={1}
      />,
    );
    await user.click(screen.getByText("Connor McDavid"));
    await user.click(screen.getByRole("button", { name: /confirm pick/i }));
    expect(onConfirm).toHaveBeenCalled();
    expect(screen.getByText("Recorded")).toBeInTheDocument();
  });
});
