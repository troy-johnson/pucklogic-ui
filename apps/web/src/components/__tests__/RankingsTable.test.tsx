/**
 * TDD tests for RankingsTable.
 * Written before the implementation.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { RankingsTable } from "../RankingsTable";
import type { ProjectedStats, RankedPlayer, Source } from "@/types";

const NULL_STATS: ProjectedStats = {
  g: null, a: null, plus_minus: null, pim: null, ppg: null, ppa: null,
  ppp: null, shg: null, sha: null, shp: null, sog: null, fow: null,
  fol: null, hits: null, blocks: null, gp: null, gs: null, w: null,
  l: null, ga: null, sa: null, sv: null, sv_pct: null, so: null, otl: null,
};

const SOURCES: Source[] = [
  { id: "s1", name: "nhl_com", display_name: "NHL.com", url: null, active: true, default_weight: null, is_paid: false },
  { id: "s2", name: "moneypuck", display_name: "MoneyPuck", url: null, active: true, default_weight: null, is_paid: false },
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
    vorp: 5.2,
    schedule_score: null,
    off_night_games: null,
    source_count: 2,
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
    vorp: 3.1,
    schedule_score: null,
    off_night_games: null,
    source_count: 2,
    projected_stats: NULL_STATS,
    breakout_score: null,
    regression_risk: null,
  },
  {
    composite_rank: 3,
    player_id: "p3",
    name: "Leon Draisaitl",
    team: "EDM",
    default_position: "C",
    platform_positions: [],
    projected_fantasy_points: 25.0,
    vorp: 1.5,
    schedule_score: null,
    off_night_games: null,
    source_count: 2,
    projected_stats: NULL_STATS,
    breakout_score: null,
    regression_risk: null,
  },
];

describe("RankingsTable", () => {
  describe("rendering", () => {
    it("renders a table element", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      expect(screen.getByRole("table")).toBeInTheDocument();
    });

    it("renders a row for each player", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      // 3 data rows + 1 header row
      const rows = screen.getAllByRole("row");
      expect(rows).toHaveLength(4);
    });

    it("renders player names", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      expect(screen.getByText("Connor McDavid")).toBeInTheDocument();
      expect(screen.getByText("Nathan MacKinnon")).toBeInTheDocument();
    });

    it("renders team abbreviations", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      const cells = screen.getAllByText("EDM");
      expect(cells.length).toBeGreaterThanOrEqual(1);
    });

    it("renders composite rank", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      expect(screen.getAllByText("1").length).toBeGreaterThan(0);
      expect(screen.getAllByText("2").length).toBeGreaterThan(0);
      expect(screen.getAllByText("3").length).toBeGreaterThan(0);
    });

    it("renders FanPts and VORP column headers", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      expect(screen.getByRole("columnheader", { name: /fanpts/i })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: /vorp/i })).toBeInTheDocument();
    });

    it("renders source count for each player", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    });

    it("shows an empty-state message when rankings list is empty", () => {
      render(<RankingsTable rankings={[]} sources={SOURCES} />);
      expect(screen.getByText(/no rankings/i)).toBeInTheDocument();
    });

    it("renders projected fantasy points formatted to 2 decimal places", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      expect(screen.getByText("30.50")).toBeInTheDocument();
    });
  });

  describe("sorting", () => {
    it("is initially sorted by composite rank ascending", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      const rows = screen.getAllByRole("row").slice(1); // skip header
      expect(rows[0]).toHaveTextContent("Connor McDavid");
      expect(rows[1]).toHaveTextContent("Nathan MacKinnon");
    });

    it("sorts by name ascending when Name header is clicked", async () => {
      const user = userEvent.setup();
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      await user.click(screen.getByRole("columnheader", { name: /name/i }));
      const rows = screen.getAllByRole("row").slice(1);
      // Alphabetical: Connor < Leon < Nathan
      expect(rows[0]).toHaveTextContent("Connor McDavid");
      expect(rows[1]).toHaveTextContent("Leon Draisaitl");
    });

    it("sorts by name descending when Name header is clicked twice", async () => {
      const user = userEvent.setup();
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      await user.click(screen.getByRole("columnheader", { name: /name/i }));
      await user.click(screen.getByRole("columnheader", { name: /name/i }));
      const rows = screen.getAllByRole("row").slice(1);
      expect(rows[0]).toHaveTextContent("Nathan MacKinnon");
    });

    it("returns to composite rank order when Rank header is clicked after sorting by name", async () => {
      const user = userEvent.setup();
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      await user.click(screen.getByRole("columnheader", { name: /name/i }));
      await user.click(screen.getByRole("columnheader", { name: /rank/i }));
      const rows = screen.getAllByRole("row").slice(1);
      expect(rows[0]).toHaveTextContent("Connor McDavid");
    });
  });
});
