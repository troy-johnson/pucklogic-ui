/**
 * TDD tests for the Dashboard page.
 * Written before the implementation.
 * Mocks: useStore (Zustand), fetchSources, computeRankings.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the store — all tests control state explicitly
vi.mock("@/store", () => ({
  useStore: vi.fn(),
}));

// Mock API modules
vi.mock("@/lib/api/sources", () => ({
  fetchSources: vi.fn(),
}));

vi.mock("@/lib/api/rankings", () => ({
  computeRankings: vi.fn(),
}));

import { useStore } from "@/store";
import { fetchSources } from "@/lib/api/sources";
import { computeRankings } from "@/lib/api/rankings";
import type { Source, RankedPlayer } from "@/types";
import DashboardPage from "../page";

const SOURCES: Source[] = [
  { id: "s1", name: "nhl_com", display_name: "NHL.com", url: null, active: true },
];

const RANKINGS: RankedPlayer[] = [
  {
    composite_rank: 1,
    composite_score: 0.95,
    player_id: "p1",
    name: "Connor McDavid",
    team: "EDM",
    position: "C",
    source_ranks: { nhl_com: 1 },
  },
];

function makeStoreMock(overrides = {}) {
  return {
    sources: [],
    weights: {},
    rankings: [],
    loading: false,
    error: null,
    cached: false,
    computedAt: null,
    season: "2025-26",
    setSources: vi.fn(),
    setWeight: vi.fn(),
    resetWeights: vi.fn(),
    activeWeights: vi.fn().mockReturnValue({}),
    setRankings: vi.fn(),
    setLoading: vi.fn(),
    setError: vi.fn(),
    clearRankings: vi.fn(),
    setSeason: vi.fn(),
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(fetchSources).mockResolvedValue(SOURCES);
  vi.mocked(computeRankings).mockResolvedValue({
    season: "2025-26",
    computed_at: "2026-03-06T00:00:00Z",
    cached: false,
    rankings: RANKINGS,
  });
  vi.mocked(useStore).mockReturnValue(makeStoreMock());
});

describe("DashboardPage", () => {
  describe("initial load", () => {
    it("renders a page heading", () => {
      render(<DashboardPage />);
      expect(screen.getByRole("heading", { name: /rankings/i })).toBeInTheDocument();
    });

    it("fetches sources on mount", async () => {
      render(<DashboardPage />);
      await waitFor(() => {
        // React 18 StrictMode may invoke effects twice in dev; assert at least once
        expect(fetchSources).toHaveBeenCalled();
      });
    });

    it("calls setSources with the fetched data", async () => {
      const setSources = vi.fn();
      vi.mocked(useStore).mockReturnValue(makeStoreMock({ setSources }));
      render(<DashboardPage />);
      await waitFor(() => {
        expect(setSources).toHaveBeenCalledWith(SOURCES);
      });
    });

    it("renders the SourceWeightSelector when sources are loaded", () => {
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({ sources: SOURCES, weights: { nhl_com: 100 } })
      );
      render(<DashboardPage />);
      expect(screen.getByRole("slider")).toBeInTheDocument();
    });

    it("does not show the rankings table before computation", () => {
      render(<DashboardPage />);
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    });
  });

  describe("compute button", () => {
    it("renders a Compute Rankings button", () => {
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({ sources: SOURCES, weights: { nhl_com: 100 } })
      );
      render(<DashboardPage />);
      expect(screen.getByRole("button", { name: /compute/i })).toBeInTheDocument();
    });

    it("calls setLoading(true) when Compute button is clicked", async () => {
      const setLoading = vi.fn();
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({ sources: SOURCES, weights: { nhl_com: 100 }, setLoading, activeWeights: vi.fn().mockReturnValue({ nhl_com: 100 }) })
      );
      const user = userEvent.setup();
      render(<DashboardPage />);
      await user.click(screen.getByRole("button", { name: /compute/i }));
      expect(setLoading).toHaveBeenCalledWith(true);
    });

    it("calls computeRankings with season and active weights", async () => {
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({
          sources: SOURCES,
          weights: { nhl_com: 100 },
          season: "2025-26",
          activeWeights: vi.fn().mockReturnValue({ nhl_com: 100 }),
        })
      );
      const user = userEvent.setup();
      render(<DashboardPage />);
      await user.click(screen.getByRole("button", { name: /compute/i }));
      expect(computeRankings).toHaveBeenCalledWith({
        season: "2025-26",
        weights: { nhl_com: 100 },
      });
    });

    it("calls setRankings with the result", async () => {
      const setRankings = vi.fn();
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({
          sources: SOURCES,
          weights: { nhl_com: 100 },
          setRankings,
          activeWeights: vi.fn().mockReturnValue({ nhl_com: 100 }),
        })
      );
      const user = userEvent.setup();
      render(<DashboardPage />);
      await user.click(screen.getByRole("button", { name: /compute/i }));
      await waitFor(() => {
        expect(setRankings).toHaveBeenCalled();
      });
    });

    it("calls setError when computeRankings throws", async () => {
      const setError = vi.fn();
      vi.mocked(computeRankings).mockRejectedValue(new Error("Server error"));
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({
          sources: SOURCES,
          weights: { nhl_com: 100 },
          setError,
          activeWeights: vi.fn().mockReturnValue({ nhl_com: 100 }),
        })
      );
      const user = userEvent.setup();
      render(<DashboardPage />);
      await user.click(screen.getByRole("button", { name: /compute/i }));
      await waitFor(() => {
        expect(setError).toHaveBeenCalledWith("Server error");
      });
    });
  });

  describe("loading state", () => {
    it("shows a loading indicator when loading is true", () => {
      vi.mocked(useStore).mockReturnValue(makeStoreMock({ loading: true }));
      render(<DashboardPage />);
      expect(screen.getByRole("status")).toBeInTheDocument();
    });

    it("disables the Compute button when loading", () => {
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({ sources: SOURCES, weights: { nhl_com: 100 }, loading: true })
      );
      render(<DashboardPage />);
      expect(screen.getByRole("button", { name: /compute/i })).toBeDisabled();
    });
  });

  describe("error state", () => {
    it("shows the error message when error is set", () => {
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({ error: "Failed to fetch rankings" })
      );
      render(<DashboardPage />);
      expect(screen.getByText("Failed to fetch rankings")).toBeInTheDocument();
    });
  });

  describe("results", () => {
    it("renders the RankingsTable when rankings are available", () => {
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({ sources: SOURCES, rankings: RANKINGS })
      );
      render(<DashboardPage />);
      expect(screen.getByRole("table")).toBeInTheDocument();
    });

    it("shows cached badge when result is from cache", () => {
      vi.mocked(useStore).mockReturnValue(
        makeStoreMock({ sources: SOURCES, rankings: RANKINGS, cached: true })
      );
      render(<DashboardPage />);
      expect(screen.getByText(/cached/i)).toBeInTheDocument();
    });
  });
});
