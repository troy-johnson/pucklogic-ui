import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mockGetUser = vi.hoisted(() =>
  vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
);

vi.mock("@supabase/ssr", () => ({
  createServerClient: vi.fn(() => ({
    auth: { getUser: mockGetUser },
  })),
}));

import { middleware } from "@/middleware";

describe("middleware redirect rules", () => {
  beforeEach(() => {
    mockGetUser.mockResolvedValue({ data: { user: null }, error: null });
  });

  it("unauthenticated request to /dashboard redirects to /login", async () => {
    const req = new NextRequest("http://localhost/dashboard");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login");
  });

  it("authenticated request to / redirects to /dashboard", async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: "u1", email: "test@test.com" } },
      error: null,
    });
    const req = new NextRequest("http://localhost/");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/dashboard");
  });

  it("unauthenticated request to / serves the landing page (no redirect)", async () => {
    const req = new NextRequest("http://localhost/");
    const res = await middleware(req);
    expect(res.status).not.toBe(307);
    expect(res.headers.get("location")).toBeNull();
  });

  it("/live is not in PUBLIC_PATHS — unauthenticated request to /live redirects to /login", async () => {
    const req = new NextRequest("http://localhost/live");
    const res = await middleware(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login");
  });

  it("preserves intended destination as ?next= on unauthenticated redirect", async () => {
    const req = new NextRequest("http://localhost/live?session=abc");
    const res = await middleware(req);
    const location = res.headers.get("location") ?? "";
    expect(location).toContain("/login");
    expect(location).toMatch(/next=/);
    expect(location).toContain(encodeURIComponent("/live"));
  });

  it("does not add ?next= when target is the default /dashboard", async () => {
    const req = new NextRequest("http://localhost/dashboard");
    const res = await middleware(req);
    const location = res.headers.get("location") ?? "";
    expect(location).toContain("/login");
    expect(location).not.toMatch(/next=/);
  });
});
