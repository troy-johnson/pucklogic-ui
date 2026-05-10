import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    auth: {
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
  })),
}));

import AppShell from "../AppShell";

describe("AppShell", () => {
  it('renders "PuckLogic" logo', () => {
    render(<AppShell passBalance={0}><div /></AppShell>);
    expect(screen.getByText("PuckLogic")).toBeInTheDocument();
  });

  it('renders passBalance prop as "N passes"', () => {
    render(<AppShell passBalance={3}><div /></AppShell>);
    expect(screen.getByText("3 passes")).toBeInTheDocument();
  });

  it('renders a button with accessible label "User menu"', () => {
    render(<AppShell passBalance={0}><div /></AppShell>);
    expect(screen.getByRole("button", { name: /user menu/i })).toBeInTheDocument();
  });
});
