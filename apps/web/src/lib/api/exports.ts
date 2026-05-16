import { ApiError, apiFetchBinary } from "./index";

type ExportDownloadType = "rankings" | "draft-sheet";
export type ExportDownloadErrorCategory =
  | "unauthenticated"
  | "no-pass"
  | "missing-context"
  | "generation-failed";

export class ExportDownloadError extends Error {
  constructor(
    public readonly category: ExportDownloadErrorCategory,
    message: string,
  ) {
    super(message);
    this.name = "ExportDownloadError";
  }
}

interface DownloadExportRequest {
  type: ExportDownloadType;
  token?: string;
  season: string;
  sourceWeights: Record<string, number>;
  scoringConfigId: string;
  platform: string;
  leagueProfileId?: string;
}

function exportTypeForDownload(type: ExportDownloadType): "excel" | "pdf" {
  return type === "rankings" ? "excel" : "pdf";
}

function safeFilenamePart(value: string): string {
  return value.replace(/[^A-Za-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase() || "export";
}

function fallbackFilename(request: DownloadExportRequest): string {
  const context = safeFilenamePart(request.scoringConfigId);
  const extension = request.type === "rankings" ? "xlsx" : "pdf";
  const generatedDate = new Date().toISOString().slice(0, 10);
  return `pucklogic-${context}-${request.type}-${generatedDate}.${extension}`;
}

function filenameFromResponse(response: Response, request: DownloadExportRequest): string {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return match?.[1] ?? fallbackFilename(request);
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function categoryForApiError(error: ApiError): ExportDownloadErrorCategory {
  if (error.status === 401) {
    return "unauthenticated";
  }

  if (error.status === 403 && error.message.toLowerCase().includes("kit pass")) {
    return "no-pass";
  }

  if ([400, 404, 422].includes(error.status)) {
    return "missing-context";
  }

  return "generation-failed";
}

function toExportDownloadError(error: unknown): ExportDownloadError {
  if (error instanceof ExportDownloadError) {
    return error;
  }

  if (error instanceof ApiError) {
    return new ExportDownloadError(categoryForApiError(error), "Export request failed");
  }

  return new ExportDownloadError("generation-failed", "Export request failed");
}

export async function downloadExport(request: DownloadExportRequest): Promise<string> {
  const exportType = exportTypeForDownload(request.type);
  const body = {
    season: request.season,
    source_weights: request.sourceWeights,
    scoring_config_id: request.scoringConfigId,
    platform: request.platform,
    ...(request.leagueProfileId ? { league_profile_id: request.leagueProfileId } : {}),
    export_type: exportType,
  };

  try {
    const response = await apiFetchBinary("/exports/generate", {
      method: "POST",
      token: request.token,
      body: JSON.stringify(body),
    });
    const blob = await response.blob();
    const filename = filenameFromResponse(response, request);
    triggerBrowserDownload(blob, filename);
    return filename;
  } catch (error) {
    throw toExportDownloadError(error);
  }
}
