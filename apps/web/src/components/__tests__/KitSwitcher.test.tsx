import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/store", () => ({
  useStore: vi.fn(),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  })),
}));

import { useStore } from "@/store";
import type { UserKit } from "@/types";
import { KitSwitcher } from "../KitSwitcher";

const KIT_A: UserKit = {
  id: "kit-a",
  name: "Playoff Kit",
  source_weights: {},
  created_at: "2026-01-01T00:00:00Z",
};
const KIT_B: UserKit = {
  id: "kit-b",
  name: "Dynasty Kit",
  source_weights: {},
  created_at: "2026-01-02T00:00:00Z",
};

function mockStore(overrides = {}) {
  vi.mocked(useStore).mockReturnValue({
    kits: [KIT_A, KIT_B],
    activeKitId: "kit-a",
    setActiveKit: vi.fn(),
    addKit: vi.fn(),
    removeKit: vi.fn(),
    updateKit: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useStore>);
}

describe("KitSwitcher", () => {
  it("renders kit names from the store", () => {
    mockStore();
    render(<KitSwitcher open onClose={vi.fn()} />);
    expect(screen.getByText("Playoff Kit")).toBeInTheDocument();
    expect(screen.getByText("Dynasty Kit")).toBeInTheDocument();
  });

  it("active kit has aria-checked=true", () => {
    mockStore();
    render(<KitSwitcher open onClose={vi.fn()} />);
    const activeRow = screen.getByRole("radio", { name: /playoff kit/i });
    expect(activeRow).toHaveAttribute("aria-checked", "true");
  });

  it('renders a "New kit" button', () => {
    mockStore();
    render(<KitSwitcher open onClose={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: /new kit/i }),
    ).toBeInTheDocument();
  });

  it("renders an overflow menu trigger for each kit", () => {
    mockStore();
    render(<KitSwitcher open onClose={vi.fn()} />);
    const menuTriggers = screen.getAllByRole("button", { name: /kit options/i });
    expect(menuTriggers).toHaveLength(2);
  });
});
