import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "../index";

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
