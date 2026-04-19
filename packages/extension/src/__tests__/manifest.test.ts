import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("extension manifest", () => {
  it("declares ESPN and Yahoo content script injection targets", () => {
    const manifestPath = resolve(process.cwd(), "manifest.json");
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as {
      content_scripts?: Array<{
        matches: string[];
        js: string[];
      }>;
    };

    expect(manifest.content_scripts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          matches: ["https://fantasy.espn.com/*"],
          js: ["espn.js"],
        }),
        expect.objectContaining({
          matches: ["https://sports.yahoo.com/*"],
          js: ["yahoo.js"],
        }),
      ]),
    );
  });
});
