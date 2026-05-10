import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/store", () => ({
  useStore: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  })),
}));

vi.mock("@/lib/api/draft-sessions", () => ({
  createSession: vi.fn(),
}));

import { useStore } from "@/store";
import { StartDraftButton } from "../StartDraftButton";

describe("StartDraftButton", () => {
  it("is disabled when no kit is active", () => {
    vi.mocked(useStore).mockImplementation((selector?: (s: { activeKitId: string | null }) => unknown) => {
      const state = { activeKitId: null, startSession: vi.fn() };
      return selector ? selector(state) : state;
    });
    render(<StartDraftButton />);
    expect(screen.getByRole("button", { name: /start draft/i })).toBeDisabled();
  });

  it("is enabled when a kit is active", () => {
    vi.mocked(useStore).mockImplementation((selector?: (s: { activeKitId: string | null }) => unknown) => {
      const state = { activeKitId: "kit-1", startSession: vi.fn() };
      return selector ? selector(state) : state;
    });
    render(<StartDraftButton />);
    expect(screen.getByRole("button", { name: /start draft/i })).not.toBeDisabled();
  });

  it("opens the StartDraftModal when clicked with an active kit", async () => {
    vi.mocked(useStore).mockImplementation((selector?: (s: { activeKitId: string | null }) => unknown) => {
      const state = { activeKitId: "kit-1", startSession: vi.fn() };
      return selector ? selector(state) : state;
    });
    const user = userEvent.setup();
    render(<StartDraftButton />);
    await user.click(screen.getByRole("button", { name: /^▶ start draft$/i }));
    expect(screen.getByRole("dialog", { name: /start live draft/i })).toBeInTheDocument();
  });
});
