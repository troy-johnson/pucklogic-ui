"use client";

import type { Source, WeightsMap } from "@/types";

interface Props {
  sources: Source[];
  weights: WeightsMap;
  setWeight: (name: string, value: number) => void;
  onReset: () => void;
  disabled?: boolean;
}

export function SourceWeightSelector({ sources, weights, setWeight, onReset, disabled = false }: Props) {
  if (sources.length === 0) return null;

  return (
    <div className="space-y-3">
      {sources.map((source) => {
        const value = weights[source.name] ?? 0;
        return (
          <div key={source.name} className="flex items-center gap-3">
            <label htmlFor={`weight-${source.name}`} className="w-32 text-sm font-medium shrink-0">
              {source.display_name}
            </label>
            <input
              id={`weight-${source.name}`}
              type="range"
              min={0}
              max={100}
              value={value}
              disabled={disabled}
              onChange={(e) => setWeight(source.name, Number(e.target.value))}
              className="flex-1 accent-blue-600"
            />
            <span className="w-8 text-right text-sm tabular-nums">{value}</span>
          </div>
        );
      })}
      <button
        type="button"
        onClick={onReset}
        disabled={disabled}
        className="mt-2 rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50 disabled:opacity-50"
      >
        Equalise Weights
      </button>
    </div>
  );
}
