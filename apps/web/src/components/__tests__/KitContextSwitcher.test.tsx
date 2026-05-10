import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/store", () => ({
  useStore: vi.fn(),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    auth: {
      getSession: vi
        .fn()
        .mockResolvedValue({ data: { session: { access_token: "tok" } } }),
    },
  })),
}));

vi.mock("@/lib/api/user-kits", () => ({
  listKits: vi.fn().mockResolvedValue([
    {
      id: "kit-1",
      name: "Playoff Kit",
      source_weights: {},
      created_at: "2026-01-01T00:00:00Z",
    },
  ]),
}));

import { useStore } from "@/store";
import { KitContextSwitcher } from "../KitContextSwitcher";

interface StoreShape {
  kits: Array<{ id: string; name: string }>;
  activeKitId: string | null;
  setKits: ReturnType<typeof vi.fn>;
  setActiveKit: ReturnType<typeof vi.fn>;
}

function mockStore(state: Partial<StoreShape> = {}) {
  const fullState: StoreShape = {
    kits: [],
    activeKitId: null,
    setKits: vi.fn(),
    setActiveKit: vi.fn(),
    ...state,
  };
  vi.mocked(useStore).mockImplementation((selector?: (s: StoreShape) => unknown) =>
    selector ? selector(fullState) : fullState,
  );
  return fullState;
}

describe("KitContextSwitcher", () => {
  it("renders 'Draft Kit' placeholder before kits are loaded", () => {
    mockStore();
    render(<KitContextSwitcher />);
    expect(screen.getByText(/draft kit/i)).toBeInTheDocument();
  });

  it("shows the active kit name when present in store", () => {
    mockStore({
      kits: [{ id: "kit-1", name: "Playoff Kit" }],
      activeKitId: "kit-1",
    });
    render(<KitContextSwitcher />);
    expect(screen.getByText("Playoff Kit")).toBeInTheDocument();
  });

  it("opens KitSwitcher drawer when the trigger is clicked", async () => {
    mockStore({
      kits: [{ id: "kit-1", name: "Playoff Kit" }],
      activeKitId: "kit-1",
    });
    const user = userEvent.setup();
    render(<KitContextSwitcher />);
    await user.click(screen.getByRole("button", { name: /playoff kit/i }));
    await waitFor(() => {
      expect(screen.getByText(/draft kits/i)).toBeInTheDocument();
    });
  });
});
