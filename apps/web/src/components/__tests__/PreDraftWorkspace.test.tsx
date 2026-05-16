import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/store", () => ({
  useStore: vi.fn(),
}));

vi.mock("@/lib/api/exports", () => ({
  downloadExport: vi.fn(),
}));

import { useStore } from "@/store";
import { downloadExport } from "@/lib/api/exports";
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

const EXPORT_CONTEXT = {
  token: "tok_abc123",
  season: "2025-26",
  scoringConfigId: "sc-1",
  platform: "espn",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

afterEach(() => vi.clearAllMocks());

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

  it("calls the export helper for rankings downloads", async () => {
    vi.mocked(downloadExport).mockResolvedValue("pucklogic-rankings.xlsx");
    mockStore();
    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialRankings={[]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /export rankings/i }));

    expect(downloadExport).toHaveBeenCalledWith({
      type: "rankings",
      token: "tok_abc123",
      season: "2025-26",
      sourceWeights: { nhl_com: 100 },
      scoringConfigId: "sc-1",
      platform: "espn",
    });
  });

  it("calls the export helper for draft sheet downloads", async () => {
    vi.mocked(downloadExport).mockResolvedValue("pucklogic-draft-sheet.pdf");
    mockStore();
    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialRankings={[]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /export draft sheet/i }));

    expect(downloadExport).toHaveBeenCalledWith({
      type: "draft-sheet",
      token: "tok_abc123",
      season: "2025-26",
      sourceWeights: { nhl_com: 100 },
      scoringConfigId: "sc-1",
      platform: "espn",
    });
  });

  it("shows loading state and prevents duplicate rankings exports", async () => {
    const pending = deferred<string>();
    vi.mocked(downloadExport).mockReturnValue(pending.promise);
    mockStore();
    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialRankings={[]}
      />,
    );

    const button = screen.getByRole("button", { name: /export rankings/i });
    await userEvent.click(button);
    await userEvent.click(button);

    expect(screen.getByRole("button", { name: /exporting rankings/i })).toBeDisabled();
    expect(downloadExport).toHaveBeenCalledOnce();
    pending.resolve("pucklogic-rankings.xlsx");
    expect(await screen.findByText(/downloaded pucklogic-rankings\.xlsx/i)).toBeInTheDocument();
  });

  it("shows a success affordance after a rankings download starts", async () => {
    vi.mocked(downloadExport).mockResolvedValue("pucklogic-rankings.xlsx");
    mockStore();
    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialRankings={[]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /export rankings/i }));

    expect(await screen.findByText(/downloaded pucklogic-rankings\.xlsx/i)).toBeInTheDocument();
  });

  it("prompts sign-in for unauthenticated export failures", async () => {
    vi.mocked(downloadExport).mockRejectedValue({ category: "unauthenticated" });
    mockStore();
    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialRankings={[]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /export rankings/i }));

    expect(await screen.findByText(/sign in to export/i)).toBeInTheDocument();
  });

  it("explains kit-pass requirement without leaking entitlement internals", async () => {
    vi.mocked(downloadExport).mockRejectedValue({
      category: "no-pass",
      message: "kit pass required",
    });
    mockStore();
    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialRankings={[]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /export rankings/i }));

    expect(await screen.findByText(/export requires an active kit pass/i)).toBeInTheDocument();
    expect(screen.queryByText(/kit pass required/i)).not.toBeInTheDocument();
  });

  it("directs users to recompute missing export context", async () => {
    vi.mocked(downloadExport).mockRejectedValue({ category: "missing-context" });
    mockStore();
    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialRankings={[]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /export rankings/i }));

    expect(await screen.findByText(/complete or recompute your kit/i)).toBeInTheDocument();
  });

  it("offers retry guidance for generation failures", async () => {
    vi.mocked(downloadExport).mockRejectedValue({ category: "generation-failed" });
    mockStore();
    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialRankings={[]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /export rankings/i }));

    expect(await screen.findByText(/export failed/i)).toBeInTheDocument();
    expect(screen.getByText(/try again/i)).toBeInTheDocument();
  });

  it("shows missing-context guidance when exportContext is not provided", async () => {
    vi.mocked(downloadExport).mockResolvedValue("pucklogic-rankings.xlsx");
    mockStore();
    render(<PreDraftWorkspace initialSources={SOURCES} initialRankings={[]} />);

    await userEvent.click(screen.getByRole("button", { name: /export rankings/i }));

    expect(await screen.findByText(/complete or recompute your kit/i)).toBeInTheDocument();
    expect(downloadExport).not.toHaveBeenCalled();
  });

  it("uses initialWeights when store weights are empty on first load", async () => {
    vi.mocked(downloadExport).mockResolvedValue("pucklogic-rankings.xlsx");
    mockStore({ sources: [], weights: {} });
    const initialWeights = { nhl_com: 100 };

    render(
      <PreDraftWorkspace
        exportContext={EXPORT_CONTEXT}
        initialSources={SOURCES}
        initialWeights={initialWeights}
        initialRankings={[]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /export rankings/i }));

    expect(downloadExport).toHaveBeenCalledWith(
      expect.objectContaining({ sourceWeights: initialWeights }),
    );
  });
});
