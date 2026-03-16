/**
 * TDD tests for SourceWeightSelector.
 * Written before the implementation — these define the component's contract.
 */
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SourceWeightSelector } from "../SourceWeightSelector";
import type { Source } from "@/types";

const SOURCES: Source[] = [
  { id: "s1", name: "nhl_com", display_name: "NHL.com", url: null, active: true, default_weight: null, is_paid: false },
  { id: "s2", name: "moneypuck", display_name: "MoneyPuck", url: null, active: true, default_weight: null, is_paid: false },
];

const WEIGHTS = { nhl_com: 60, moneypuck: 40 };

describe("SourceWeightSelector", () => {
  describe("rendering", () => {
    it("renders a slider for each source", () => {
      render(
        <SourceWeightSelector
          sources={SOURCES}
          weights={WEIGHTS}
          setWeight={vi.fn()}
          onReset={vi.fn()}
        />
      );
      const sliders = screen.getAllByRole("slider");
      expect(sliders).toHaveLength(2);
    });

    it("renders each source's display_name", () => {
      render(
        <SourceWeightSelector
          sources={SOURCES}
          weights={WEIGHTS}
          setWeight={vi.fn()}
          onReset={vi.fn()}
        />
      );
      expect(screen.getByText("NHL.com")).toBeInTheDocument();
      expect(screen.getByText("MoneyPuck")).toBeInTheDocument();
    });

    it("sets slider value from weights prop", () => {
      render(
        <SourceWeightSelector
          sources={SOURCES}
          weights={WEIGHTS}
          setWeight={vi.fn()}
          onReset={vi.fn()}
        />
      );
      const sliders = screen.getAllByRole("slider");
      const values = sliders.map((s) => Number(s.getAttribute("value") ?? s.getAttribute("aria-valuenow")));
      expect(values).toContain(60);
      expect(values).toContain(40);
    });

    it("displays the current weight value next to each slider", () => {
      render(
        <SourceWeightSelector
          sources={SOURCES}
          weights={WEIGHTS}
          setWeight={vi.fn()}
          onReset={vi.fn()}
        />
      );
      expect(screen.getByText("60")).toBeInTheDocument();
      expect(screen.getByText("40")).toBeInTheDocument();
    });

    it("renders an Equalise button", () => {
      render(
        <SourceWeightSelector
          sources={SOURCES}
          weights={WEIGHTS}
          setWeight={vi.fn()}
          onReset={vi.fn()}
        />
      );
      expect(screen.getByRole("button", { name: /equalise/i })).toBeInTheDocument();
    });

    it("renders nothing when sources list is empty", () => {
      const { container } = render(
        <SourceWeightSelector
          sources={[]}
          weights={{}}
          setWeight={vi.fn()}
          onReset={vi.fn()}
        />
      );
      expect(container.firstChild).toBeNull();
    });

    it("disables all sliders when disabled prop is true", () => {
      render(
        <SourceWeightSelector
          sources={SOURCES}
          weights={WEIGHTS}
          setWeight={vi.fn()}
          onReset={vi.fn()}
          disabled
        />
      );
      screen.getAllByRole("slider").forEach((s) => {
        expect(s).toBeDisabled();
      });
    });

    it("disables the Equalise button when disabled prop is true", () => {
      render(
        <SourceWeightSelector
          sources={SOURCES}
          weights={WEIGHTS}
          setWeight={vi.fn()}
          onReset={vi.fn()}
          disabled
        />
      );
      expect(screen.getByRole("button", { name: /equalise/i })).toBeDisabled();
    });
  });

  describe("interactions", () => {
    it("calls setWeight with source name and numeric value when slider changes", () => {
      const setWeight = vi.fn();
      render(
        <SourceWeightSelector
          sources={[SOURCES[0]]}
          weights={{ nhl_com: 50 }}
          setWeight={setWeight}
          onReset={vi.fn()}
        />
      );
      const slider = screen.getByRole("slider");
      fireEvent.change(slider, { target: { value: "75" } });
      expect(setWeight).toHaveBeenCalledWith("nhl_com", 75);
    });

    it("calls onReset when the Equalise button is clicked", async () => {
      const onReset = vi.fn();
      const user = userEvent.setup();
      render(
        <SourceWeightSelector
          sources={SOURCES}
          weights={WEIGHTS}
          setWeight={vi.fn()}
          onReset={onReset}
        />
      );
      await user.click(screen.getByRole("button", { name: /equalise/i }));
      expect(onReset).toHaveBeenCalledTimes(1);
    });
  });
});
