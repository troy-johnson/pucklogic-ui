import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: mockPush })),
}));

vi.mock("@/store", () => ({
  useStore: vi.fn().mockReturnValue({
    startSession: vi.fn(),
  }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "token-123" } },
      }),
    },
  })),
}));

vi.mock("@/lib/api/draft-sessions", () => ({
  createSession: vi.fn().mockResolvedValue({ session_id: "sess-abc" }),
}));

import { StartDraftModal } from "../StartDraftModal";
import { createSession } from "@/lib/api/draft-sessions";

describe("StartDraftModal", () => {
  it("renders confirmation text and confirm button", () => {
    render(<StartDraftModal kitId="kit-1" onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: /start draft/i })).toBeInTheDocument();
  });

  it("calls createSession on confirm", async () => {
    const user = userEvent.setup();
    render(<StartDraftModal kitId="kit-1" onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /start draft/i }));
    expect(vi.mocked(createSession)).toHaveBeenCalledWith(
      expect.objectContaining({ kitId: "kit-1" }),
      "token-123",
    );
  });

  it("calls router.push('/live') on success", async () => {
    const user = userEvent.setup();
    render(<StartDraftModal kitId="kit-1" onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /start draft/i }));
    expect(mockPush).toHaveBeenCalledWith("/live");
  });
});
