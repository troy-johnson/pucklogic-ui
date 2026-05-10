"use client";

import { useState } from "react";
import { RankingsTable } from "./RankingsTable";
import { SourceWeightSelector } from "./SourceWeightSelector";
import { useStore } from "@/store";
import type { RankedPlayer, Source } from "@/types";

const POSITIONS = ["All", "C", "LW", "RW", "D", "G"] as const;
type Position = (typeof POSITIONS)[number];

interface Props {
  initialSources: Source[];
  initialRankings?: RankedPlayer[];
}

export function PreDraftWorkspace({
  initialSources,
  initialRankings = [],
}: Props) {
  const { sources, weights, setWeight, resetWeights } = useStore();
  const [rankings] = useState<RankedPlayer[]>(initialRankings);
  const [activePosition, setActivePosition] = useState<Position>("All");

  const displaySources = sources.length > 0 ? sources : initialSources;

  const filteredRankings =
    activePosition === "All"
      ? rankings
      : rankings.filter(
          (p) =>
            p.default_position === activePosition ||
            p.platform_positions.includes(activePosition),
        );

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
          <button className="pl-btn-secondary rounded py-2 text-sm">
            Export rankings
          </button>
          <button className="pl-btn-ghost rounded py-2 text-sm">
            Export draft sheet
          </button>
        </div>
      </aside>
    </div>
  );
}
