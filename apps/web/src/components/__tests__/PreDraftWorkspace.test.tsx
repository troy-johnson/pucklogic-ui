import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/store", () => ({
  useStore: vi.fn(),
}));

import { useStore } from "@/store";
import type { Source, RankedPlayer } from "@/types";
import { PreDraftWorkspace } from "../PreDraftWorkspace";

const SOURCES: Source[] = [
  {
    id: "s1",
    name: "nhl_com",
    display_name: "NHL.com",
    url: null,
    active: true,
    default_weight: null,
    is_paid: false,
  },
];

const RANKINGS: RankedPlayer[] = [
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
    projected_stats: {
      g: null, a: null, plus_minus: null, pim: null, ppg: null,
      ppa: null, ppp: null, shg: null, sha: null, shp: null, sog: null,
      fow: null, fol: null, hits: null, blocks: null, gp: null, gs: null,
      w: null, l: null, ga: null, sa: null, sv: null, sv_pct: null,
      so: null, otl: null,
    },
    breakout_score: null,
    regression_risk: null,
  },
];

function mockStore(overrides = {}) {
  vi.mocked(useStore).mockReturnValue({
    sources: SOURCES,
    weights: { nhl_com: 100 },
    setWeight: vi.fn(),
    resetWeights: vi.fn(),
    activeWeights: vi.fn().mockReturnValue({ nhl_com: 100 }),
    ...overrides,
  } as ReturnType<typeof useStore>);
}

describe("PreDraftWorkspace", () => {
  it("renders RankingsTable with player data", () => {
    mockStore();
    render(<PreDraftWorkspace initialSources={SOURCES} initialRankings={RANKINGS} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Connor McDavid")).toBeInTheDocument();
  });

  it("renders source weight sliders in the right panel", () => {
    mockStore();
    render(<PreDraftWorkspace initialSources={SOURCES} initialRankings={[]} />);
    expect(screen.getByLabelText("NHL.com")).toBeInTheDocument();
  });

  it('renders "Export rankings" button', () => {
    mockStore();
    render(<PreDraftWorkspace initialSources={SOURCES} initialRankings={[]} />);
    expect(
      screen.getByRole("button", { name: /export rankings/i }),
    ).toBeInTheDocument();
  });

  it('renders "Export draft sheet" button', () => {
    mockStore();
    render(<PreDraftWorkspace initialSources={SOURCES} initialRankings={[]} />);
    expect(
      screen.getByRole("button", { name: /export draft sheet/i }),
    ).toBeInTheDocument();
  });
});
