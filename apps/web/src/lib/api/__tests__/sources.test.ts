/**
 * TDD tests for src/lib/api/sources.ts
 * Written BEFORE the implementation — these define the expected API surface.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchSources } from "@/lib/api/sources";

const BASE = "http://localhost:8000";

const MOCK_SOURCES = [
  { id: "s1", name: "nhl_com", display_name: "NHL.com", url: null, active: true },
  { id: "s2", name: "moneypuck", display_name: "MoneyPuck", url: null, active: true },
];

beforeEach(() => {
  vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify(MOCK_SOURCES), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  );
});

afterEach(() => vi.restoreAllMocks());

describe("fetchSources", () => {
  it("calls GET /sources", async () => {
    await fetchSources();
    expect(fetch).toHaveBeenCalledTimes(1);
    const url = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
    expect(url).toContain("/sources");
  });

  it("passes active_only=true by default", async () => {
    await fetchSources();
    const url = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
    expect(url).toContain("active_only=true");
  });

  it("passes active_only=false when requested", async () => {
    await fetchSources(false);
    const url = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
    expect(url).toContain("active_only=false");
  });

  it("returns an array of Source objects", async () => {
    const result = await fetchSources();
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("nhl_com");
    expect(result[0].display_name).toBe("NHL.com");
  });

  it("hits the configured API base URL", async () => {
    await fetchSources();
    const url = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
    expect(url.startsWith(BASE)).toBe(true);
  });
});
