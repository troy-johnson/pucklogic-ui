import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadExport } from "../exports";

const BASE = "http://localhost:8000";

function mockSuccessfulExport(contentDisposition?: string) {
  return vi.spyOn(global, "fetch").mockResolvedValueOnce({
    ok: true,
    status: 200,
    headers: new Headers(
      contentDisposition
        ? {
            "Content-Disposition": contentDisposition,
          }
        : {},
    ),
    blob: async () => new Blob(["EXPORT"]),
  } as Response);
}

function mockFailedExport(status: number, body: string) {
  return vi.spyOn(global, "fetch").mockResolvedValueOnce({
    ok: false,
    status,
    text: async () => body,
  } as Response);
}

const REQUEST = {
  type: "rankings" as const,
  token: "tok_abc123",
  season: "2025-26",
  sourceWeights: { nhl_com: 100 },
  scoringConfigId: "sc-1",
  platform: "espn",
};

function mockBrowserDownloadApis() {
  const click = vi.fn();
  const anchor = {
    click,
    href: "",
    download: "",
    remove: vi.fn(),
  } as unknown as HTMLAnchorElement;

  vi.spyOn(document, "createElement").mockReturnValue(anchor);
  vi.spyOn(document.body, "appendChild").mockImplementation((node) => node);
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:pucklogic-export");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

  return { anchor, click };
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("downloadExport", () => {
  it("posts rankings requests as backend excel exports", async () => {
    const fetchSpy = mockSuccessfulExport();
    mockBrowserDownloadApis();

    await downloadExport({
      type: "rankings",
      token: "tok_abc123",
      season: "2025-26",
      sourceWeights: { nhl_com: 100 },
      scoringConfigId: "sc-1",
      platform: "espn",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/exports/generate`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          season: "2025-26",
          source_weights: { nhl_com: 100 },
          scoring_config_id: "sc-1",
          platform: "espn",
          export_type: "excel",
        }),
      }),
    );
  });

  it("posts draft sheet requests as backend pdf exports", async () => {
    const fetchSpy = mockSuccessfulExport();
    mockBrowserDownloadApis();

    await downloadExport({
      type: "draft-sheet",
      token: "tok_abc123",
      season: "2025-26",
      sourceWeights: { nhl_com: 100 },
      scoringConfigId: "sc-1",
      platform: "espn",
      leagueProfileId: "lp-1",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/exports/generate`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          season: "2025-26",
          source_weights: { nhl_com: 100 },
          scoring_config_id: "sc-1",
          platform: "espn",
          league_profile_id: "lp-1",
          export_type: "pdf",
        }),
      }),
    );
  });

  it("uses the response attachment filename for the browser download", async () => {
    mockSuccessfulExport('attachment; filename="pucklogic-sc-1-rankings-2026-05-11.xlsx"');
    const { anchor, click } = mockBrowserDownloadApis();

    const filename = await downloadExport({
      type: "rankings",
      token: "tok_abc123",
      season: "2025-26",
      sourceWeights: { nhl_com: 100 },
      scoringConfigId: "sc-1",
      platform: "espn",
    });

    expect(filename).toBe("pucklogic-sc-1-rankings-2026-05-11.xlsx");
    expect(anchor.download).toBe("pucklogic-sc-1-rankings-2026-05-11.xlsx");
    expect(anchor.href).toBe("blob:pucklogic-export");
    expect(click).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:pucklogic-export");
  });

  it("builds a sanitized fallback filename when the response has no attachment filename", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-11T15:30:00Z"));
    mockSuccessfulExport();
    const { anchor } = mockBrowserDownloadApis();

    const filename = await downloadExport({
      type: "draft-sheet",
      token: "tok_abc123",
      season: "2025-26",
      sourceWeights: { nhl_com: 100 },
      scoringConfigId: "Kit:Bad/Name",
      platform: "espn",
    });

    expect(filename).toBe("pucklogic-kit-bad-name-draft-sheet-2026-05-11.pdf");
    expect(anchor.download).toBe("pucklogic-kit-bad-name-draft-sheet-2026-05-11.pdf");
  });

  it("maps unauthenticated responses to an unauthenticated export category", async () => {
    mockFailedExport(401, "Missing or invalid Authorization header");

    await expect(downloadExport(REQUEST)).rejects.toMatchObject({
      category: "unauthenticated",
    });
  });

  it("maps kit-pass responses to a no-pass export category", async () => {
    mockFailedExport(403, "kit pass required");

    await expect(downloadExport(REQUEST)).rejects.toMatchObject({
      category: "no-pass",
    });
  });

  it("maps request context responses to a missing-context export category", async () => {
    mockFailedExport(404, "Scoring config not found");

    await expect(downloadExport(REQUEST)).rejects.toMatchObject({
      category: "missing-context",
    });
  });

  it("maps unexpected failures to a generation-failed export category", async () => {
    mockFailedExport(500, "database traceback with internals");

    await expect(downloadExport(REQUEST)).rejects.toMatchObject({
      category: "generation-failed",
    });
  });
});
