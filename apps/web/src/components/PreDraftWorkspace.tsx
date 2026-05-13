"use client";

import { useState } from "react";
import { RankingsTable } from "./RankingsTable";
import { SourceWeightSelector } from "./SourceWeightSelector";
import { downloadExport } from "@/lib/api/exports";
import { useStore } from "@/store";
import type { RankedPlayer, Source } from "@/types";

const POSITIONS = ["All", "C", "LW", "RW", "D", "G"] as const;
type Position = (typeof POSITIONS)[number];
type ExportType = "rankings" | "draft-sheet";
type ExportErrorCategory =
  | "unauthenticated"
  | "no-pass"
  | "missing-context"
  | "generation-failed";

interface Props {
  initialSources: Source[];
  initialRankings?: RankedPlayer[];
  exportContext?: {
    token?: string;
    season: string;
    scoringConfigId: string;
    platform: string;
    leagueProfileId?: string;
  };
}

function exportErrorCategory(error: unknown): ExportErrorCategory {
  if (
    typeof error === "object" &&
    error !== null &&
    "category" in error &&
    typeof error.category === "string"
  ) {
    const category = error.category;
    if (
      category === "unauthenticated" ||
      category === "no-pass" ||
      category === "missing-context" ||
      category === "generation-failed"
    ) {
      return category;
    }
  }

  return "generation-failed";
}

function exportErrorMessage(error: unknown): string {
  switch (exportErrorCategory(error)) {
    case "unauthenticated":
      return "Sign in to export your draft kit.";
    case "no-pass":
      return "Export requires an active kit pass.";
    case "missing-context":
      return "Complete or recompute your kit before exporting.";
    case "generation-failed":
      return "Export failed. Try again.";
  }
}

export function PreDraftWorkspace({
  initialSources,
  initialRankings = [],
  exportContext,
}: Props) {
  const { sources, weights, setWeight, resetWeights } = useStore();
  const [rankings] = useState<RankedPlayer[]>(initialRankings);
  const [activePosition, setActivePosition] = useState<Position>("All");
  const [exporting, setExporting] = useState<ExportType | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  const displaySources = sources.length > 0 ? sources : initialSources;

  const filteredRankings =
    activePosition === "All"
      ? rankings
      : rankings.filter(
          (p) =>
            p.default_position === activePosition ||
            p.platform_positions.includes(activePosition),
        );

  async function handleExport(type: ExportType) {
    if (exporting === type) {
      return;
    }

    if (!exportContext) {
      setExportMessage(exportErrorMessage({ category: "missing-context" }));
      return;
    }

    setExporting(type);
    setExportMessage(null);
    try {
      const filename = await downloadExport({
        type,
        token: exportContext.token,
        season: exportContext.season,
        sourceWeights: weights,
        scoringConfigId: exportContext.scoringConfigId,
        platform: exportContext.platform,
        leagueProfileId: exportContext.leagueProfileId,
      });
      setExportMessage(`Downloaded ${filename}`);
    } catch (error) {
      setExportMessage(exportErrorMessage(error));
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Main content — rankings table */}
      <div className="flex flex-1 flex-col overflow-auto p-4">
        {/* Position filter pills */}
        <div className="mb-4 flex gap-1.5">
          {POSITIONS.map((pos) => (
            <button
              key={pos}
              className="pl-pill rounded-pill px-3 py-1 text-xs"
              data-active={activePosition === pos}
              onClick={() => setActivePosition(pos)}
            >
              {pos}
            </button>
          ))}
        </div>

        <RankingsTable rankings={filteredRankings} sources={displaySources} />
      </div>

      {/* Right panel — source weights + exports */}
      <aside className="flex w-72 flex-col gap-4 border-l border-border-subtle bg-bg-surface p-4">
        <section>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            Source Weights
          </h3>
          <SourceWeightSelector
            sources={displaySources}
            weights={weights}
            setWeight={setWeight}
            onReset={resetWeights}
          />
        </section>

        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            League Profile
          </h3>
          <p className="text-xs text-text-secondary">
            No league configured — Add league
          </p>
        </section>

        <div className="mt-auto flex flex-col gap-2">
          {exportMessage ? (
            <p className="text-xs text-text-secondary" role="status">
              {exportMessage}
            </p>
          ) : null}
          <button
            className="pl-btn-secondary rounded py-2 text-sm"
            disabled={exporting === "rankings"}
            onClick={() => void handleExport("rankings")}
          >
            {exporting === "rankings" ? "Exporting rankings" : "Export rankings"}
          </button>
          <button
            className="pl-btn-ghost rounded py-2 text-sm"
            disabled={exporting === "draft-sheet"}
            onClick={() => void handleExport("draft-sheet")}
          >
            {exporting === "draft-sheet" ? "Exporting draft sheet" : "Export draft sheet"}
          </button>
        </div>
      </aside>
    </div>
  );
}
