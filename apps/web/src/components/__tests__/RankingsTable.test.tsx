/**
 * TDD tests for RankingsTable.
 * Written before the implementation.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RankingsTable } from "../RankingsTable";
import type { RankedPlayer, Source } from "@/types";

const SOURCES: Source[] = [
  { id: "s1", name: "nhl_com", display_name: "NHL.com", url: null, active: true },
  { id: "s2", name: "moneypuck", display_name: "MoneyPuck", url: null, active: true },
];

const RANKINGS: RankedPlayer[] = [
  {
    composite_rank: 1,
    composite_score: 0.95,
    player_id: "p1",
    name: "Connor McDavid",
    team: "EDM",
    position: "C",
    source_ranks: { nhl_com: 1, moneypuck: 2 },
  },
  {
    composite_rank: 2,
    composite_score: 0.88,
    player_id: "p2",
    name: "Nathan MacKinnon",
    team: "COL",
    position: "C",
    source_ranks: { nhl_com: 2, moneypuck: 1 },
  },
  {
    composite_rank: 3,
    composite_score: 0.80,
    player_id: "p3",
    name: "Leon Draisaitl",
    team: "EDM",
    position: "C",
    source_ranks: { nhl_com: 3, moneypuck: 3 },
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
      // Multiple "1"s exist (rank col + source rank cols) — just assert presence
      expect(screen.getAllByText("1").length).toBeGreaterThan(0);
      expect(screen.getAllByText("2").length).toBeGreaterThan(0);
      expect(screen.getAllByText("3").length).toBeGreaterThan(0);
    });

    it("renders a column header for each source", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      expect(screen.getByRole("columnheader", { name: "NHL.com" })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: "MoneyPuck" })).toBeInTheDocument();
    });

    it("renders source-specific rank for each player", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      // McDavid is nhl_com rank 1 and moneypuck rank 2
      const mcdRow = screen.getByText("Connor McDavid").closest("tr")!;
      expect(within(mcdRow).getAllByText("1")[0]).toBeInTheDocument();
      expect(within(mcdRow).getByText("2")).toBeInTheDocument();
    });

    it("shows an empty-state message when rankings list is empty", () => {
      render(<RankingsTable rankings={[]} sources={SOURCES} />);
      expect(screen.getByText(/no rankings/i)).toBeInTheDocument();
    });

    it("renders composite score formatted to 2 decimal places", () => {
      render(<RankingsTable rankings={RANKINGS} sources={SOURCES} />);
      expect(screen.getByText("0.95")).toBeInTheDocument();
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
