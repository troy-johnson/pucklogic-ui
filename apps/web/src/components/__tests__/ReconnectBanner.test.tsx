import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/store", () => ({
  useStore: vi.fn(),
}));

import { useStore } from "@/store";
import { ReconnectBanner } from "../ReconnectBanner";

function mockStore(mode: string, setMode = vi.fn()) {
  vi.mocked(useStore).mockReturnValue({
    mode,
    setMode,
  } as ReturnType<typeof useStore>);
}

describe("ReconnectBanner", () => {
  it("is visible when mode is reconnecting", () => {
    mockStore("reconnecting");
    render(<ReconnectBanner />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("is visible when mode is disconnected", () => {
    mockStore("disconnected");
    render(<ReconnectBanner />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("is hidden when mode is sync", () => {
    mockStore("sync");
    render(<ReconnectBanner />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it('dispatches setMode("manual") when "Switch to manual" is clicked', async () => {
    const setMode = vi.fn();
    mockStore("reconnecting", setMode);
    const user = userEvent.setup();
    render(<ReconnectBanner />);
    await user.click(screen.getByRole("button", { name: /switch to manual/i }));
    expect(setMode).toHaveBeenCalledWith("manual");
  });
});
