/**
 * Tests for (auth)/dashboard/page.tsx — Server Component wrapper.
 *
 * The page is an async Server Component that fetches sources and renders
 * PreDraftWorkspace. Comprehensive interaction tests live in
 * PreDraftWorkspace.test.tsx and RankingsTable.test.tsx.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/api/sources", () => ({
  fetchSources: vi.fn().mockResolvedValue([
    {
      id: "s1",
      name: "nhl_com",
      display_name: "NHL.com",
      url: null,
      active: true,
      default_weight: null,
      is_paid: false,
    },
  ]),
}));

vi.mock("@/store", () => ({
  useStore: vi.fn().mockReturnValue({
    sources: [],
    weights: {},
    setWeight: vi.fn(),
    resetWeights: vi.fn(),
    activeWeights: vi.fn().mockReturnValue({}),
    kits: [],
    activeKitId: null,
  }),
}));

import DashboardPage from "../page";

describe("DashboardPage (Server Component)", () => {
  it("renders without crashing and shows the workspace", async () => {
    const element = await DashboardPage();
    render(element);
    expect(
      screen.getByRole("button", { name: /export rankings/i }),
    ).toBeInTheDocument();
  });

  it("renders the export buttons", async () => {
    const element = await DashboardPage();
    render(element);
    expect(
      screen.getByRole("button", { name: /export rankings/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /export draft sheet/i }),
    ).toBeInTheDocument();
  });
});
