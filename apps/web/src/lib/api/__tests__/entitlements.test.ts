import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/index", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api/index";
import { fetchEntitlements } from "@/lib/api/entitlements";

afterEach(() => vi.restoreAllMocks());

describe("fetchEntitlements", () => {
  it("calls apiFetch with /entitlements and token", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      kit_pass: true,
      draft_passes: 2,
    });

    const result = await fetchEntitlements("test-token");

    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith("/entitlements", {
      token: "test-token",
    });
    expect(result.kit_pass).toBe(true);
    expect(result.draft_passes).toBe(2);
  });
});
