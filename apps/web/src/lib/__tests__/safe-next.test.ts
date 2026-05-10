import { describe, expect, it } from "vitest";
import { safeNextPath } from "@/lib/safe-next";

describe("safeNextPath", () => {
  it("returns the fallback for null/undefined/empty input", () => {
    expect(safeNextPath(null)).toBe("/dashboard");
    expect(safeNextPath(undefined)).toBe("/dashboard");
    expect(safeNextPath("")).toBe("/dashboard");
  });

  it("accepts well-formed relative paths", () => {
    expect(safeNextPath("/live")).toBe("/live");
    expect(safeNextPath("/dashboard?foo=bar")).toBe("/dashboard?foo=bar");
  });

  it("rejects protocol-relative URLs", () => {
    expect(safeNextPath("//evil.com")).toBe("/dashboard");
    expect(safeNextPath("/\\evil.com")).toBe("/dashboard");
  });

  it("rejects absolute URLs", () => {
    expect(safeNextPath("https://evil.com/dashboard")).toBe("/dashboard");
    expect(safeNextPath("dashboard")).toBe("/dashboard");
  });

  it("honors an explicit fallback", () => {
    expect(safeNextPath(null, "/")).toBe("/");
    expect(safeNextPath("//attacker", "/login")).toBe("/login");
  });
});
