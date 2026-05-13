import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, apiFetchBinary } from "../index";

const BASE = "http://localhost:8000";

function mockFetch(response: Partial<Response>) {
  return vi.spyOn(global, "fetch").mockResolvedValueOnce(response as Response);
}

afterEach(() => vi.restoreAllMocks());

describe("apiFetch", () => {
  describe("successful responses", () => {
    it("returns parsed JSON", async () => {
      mockFetch({ ok: true, json: async () => ({ status: "ok" }) });
      expect(await apiFetch<{ status: string }>("/health")).toEqual({
        status: "ok",
      });
    });

    it("returns undefined for a 204 No Content response", async () => {
      mockFetch({ ok: true, status: 204 });
      const result = await apiFetch<undefined>("/user-kits/kit-1");
      expect(result).toBeUndefined();
    });

    it("calls the correct URL", async () => {
      const spy = mockFetch({ ok: true, json: async () => ({}) });
      await apiFetch("/health");
      expect(spy).toHaveBeenCalledWith(`${BASE}/health`, expect.any(Object));
    });

    it("sets Content-Type: application/json by default", async () => {
      const spy = mockFetch({ ok: true, json: async () => ({}) });
      await apiFetch("/health");
      const [, opts] = spy.mock.calls[0];
      expect((opts as RequestInit).headers).toMatchObject({
        "Content-Type": "application/json",
      });
    });
  });

  describe("auth header", () => {
    it("attaches Bearer token when token option is provided", async () => {
      const spy = mockFetch({ ok: true, json: async () => ({}) });
      await apiFetch("/players", { token: "tok_abc123" });
      const [, opts] = spy.mock.calls[0];
      expect((opts as RequestInit).headers).toMatchObject({
        Authorization: "Bearer tok_abc123",
      });
    });

    it("omits Authorization header when no token provided", async () => {
      const spy = mockFetch({ ok: true, json: async () => ({}) });
      await apiFetch("/health");
      const [, opts] = spy.mock.calls[0];
      expect((opts as RequestInit).headers).not.toHaveProperty("Authorization");
    });
  });

  describe("error handling", () => {
    it("throws ApiError on a 4xx response", async () => {
      mockFetch({ ok: false, status: 404, text: async () => "Not Found" });
      await expect(apiFetch("/missing")).rejects.toBeInstanceOf(ApiError);
    });

    it("includes the HTTP status on ApiError", async () => {
      mockFetch({ ok: false, status: 403, text: async () => "Forbidden" });
      const err = (await apiFetch("/secret").catch((e: unknown) => e as ApiError)) as ApiError;
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(403);
    });

    it("includes the response body in the error message", async () => {
      mockFetch({ ok: false, status: 422, text: async () => "Unprocessable" });
      const err = (await apiFetch("/broken").catch((e: unknown) => e as ApiError)) as ApiError;
      expect(err.message).toBe("Unprocessable");
    });
  });
});

describe("apiFetchBinary", () => {
  it("returns the raw response for successful binary downloads", async () => {
    const blob = new Blob(["XLSXDATA"], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const response = {
      ok: true,
      status: 200,
      headers: new Headers({
        "Content-Disposition": 'attachment; filename="pucklogic-rankings.xlsx"',
      }),
      blob: async () => blob,
    } as Response;
    mockFetch(response);

    const result = await apiFetchBinary("/exports/generate", {
      method: "POST",
      token: "tok_abc123",
      body: JSON.stringify({ export_type: "excel" }),
    });

    expect(result).toBe(response);
    await expect(result.blob()).resolves.toBe(blob);
    expect(result.headers.get("Content-Disposition")).toBe(
      'attachment; filename="pucklogic-rankings.xlsx"',
    );
  });

  it("preserves JSON content-type and auth headers without parsing JSON", async () => {
    const spy = mockFetch({ ok: true, status: 200, blob: async () => new Blob(["PDF"]) });

    await apiFetchBinary("/exports/generate", {
      method: "POST",
      token: "tok_abc123",
      body: JSON.stringify({ export_type: "pdf" }),
    });

    const [, opts] = spy.mock.calls[0];
    expect((opts as RequestInit).headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer tok_abc123",
    });
  });

  it("throws ApiError on failed binary responses", async () => {
    mockFetch({ ok: false, status: 403, text: async () => "kit pass required" });

    await expect(apiFetchBinary("/exports/generate")).rejects.toMatchObject({
      status: 403,
      message: "kit pass required",
    });
  });
});
