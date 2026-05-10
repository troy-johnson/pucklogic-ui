import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/store", () => ({
  useStore: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

import { useStore } from "@/store";
import { LiveDraftScreen } from "../LiveDraftScreen";
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

function mockStore(overrides = {}) {
  vi.mocked(useStore).mockReturnValue({
    picks: [],
    mode: "sync",
    sessionId: "sess-1",
    setMode: vi.fn(),
    recordPick: vi.fn(),
    hydrateSession: vi.fn(),
    endSession: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useStore>);
}

describe("LiveDraftScreen", () => {
  it('renders "Available players" heading', () => {
    mockStore();
    render(<LiveDraftScreen players={PLAYERS} myTeamPlayers={[]} />);
    expect(screen.getByText(/available players/i)).toBeInTheDocument();
  });

  it("renders at least one suggestion card", () => {
    mockStore();
    render(<LiveDraftScreen players={PLAYERS} myTeamPlayers={[]} />);
    expect(screen.getByText(/priority pick/i)).toBeInTheDocument();
  });

  it('renders "Roster needs" heading', () => {
    mockStore();
    render(<LiveDraftScreen players={PLAYERS} myTeamPlayers={[]} />);
    expect(screen.getByText(/roster needs/i)).toBeInTheDocument();
  });

  it("renders a sync status indicator", () => {
    mockStore();
    render(<LiveDraftScreen players={PLAYERS} myTeamPlayers={[]} />);
    expect(screen.getByTestId("sync-status")).toBeInTheDocument();
  });
});
