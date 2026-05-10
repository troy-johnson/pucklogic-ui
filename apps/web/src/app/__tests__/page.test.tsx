import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import LandingPage from "../page";

describe("Landing page", () => {
  it('does not render "Coming soon" text', () => {
    render(<LandingPage />);
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
  });

  it('renders "PuckLogic" logo in nav', () => {
    render(<LandingPage />);
    expect(screen.getAllByText("PuckLogic").length).toBeGreaterThan(0);
  });

  it('renders "01" in the steps strip', () => {
    render(<LandingPage />);
    expect(screen.getByText("01")).toBeInTheDocument();
  });

  it("renders at least one primary CTA link", () => {
    render(<LandingPage />);
    const ctaLinks = screen.getAllByRole("link", {
      name: /start|kit|sign in|get started|free/i,
    });
    expect(ctaLinks.length).toBeGreaterThan(0);
  });
});
