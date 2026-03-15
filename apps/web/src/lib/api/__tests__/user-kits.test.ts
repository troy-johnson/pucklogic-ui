/**
 * TDD tests for src/lib/api/user-kits.ts
 * Written BEFORE the implementation — these define the expected API surface.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createUserKit, deleteUserKit, fetchUserKits } from "@/lib/api/user-kits";

const KIT = {
  id: "kit-1",
  name: "My Kit",
  source_weights: { nhl_com: 60, moneypuck: 40 },
  created_at: "2026-03-01T00:00:00Z",
};

function mockFetch(body: unknown, status = 200) {
  vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: status === 204 ? {} : { "Content-Type": "application/json" },
    })
  );
}

afterEach(() => vi.restoreAllMocks());

describe("fetchUserKits", () => {
  beforeEach(() => mockFetch([KIT]));

  it("calls GET /user-kits", async () => {
    await fetchUserKits();
    const url = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
    expect(url).toContain("/user-kits");
    const [, init] = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0] as [string, RequestInit | undefined];
    expect((init?.method ?? "GET").toUpperCase()).toBe("GET");
  });

  it("returns an array of UserKit objects", async () => {
    const kits = await fetchUserKits();
    expect(kits).toHaveLength(1);
    expect(kits[0].id).toBe("kit-1");
    expect(kits[0].source_weights).toEqual({ nhl_com: 60, moneypuck: 40 });
  });
});

describe("createUserKit", () => {
  beforeEach(() => mockFetch(KIT, 201));

  const REQ = { name: "My Kit", source_weights: { nhl_com: 60 } };

  it("calls POST /user-kits", async () => {
    await createUserKit(REQ);
    const [url, init] = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/user-kits");
    expect(init.method).toBe("POST");
  });

  it("sends the request body as JSON", async () => {
    await createUserKit(REQ);
    const [, init] = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.name).toBe("My Kit");
    expect(body.source_weights).toEqual({ nhl_com: 60 });
  });

  it("returns the created UserKit", async () => {
    const kit = await createUserKit(REQ);
    expect(kit.id).toBe("kit-1");
    expect(kit.created_at).toBeTruthy();
  });
});

describe("deleteUserKit", () => {
  beforeEach(() => mockFetch(null, 204));

  it("calls DELETE /user-kits/:id", async () => {
    await deleteUserKit("kit-1");
    const [url, init] = (fetch as ReturnType<typeof vi.spyOn>).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/user-kits/kit-1");
    expect(init.method).toBe("DELETE");
  });

  it("resolves without returning a value", async () => {
    const result = await deleteUserKit("kit-1");
    expect(result).toBeUndefined();
  });
});
