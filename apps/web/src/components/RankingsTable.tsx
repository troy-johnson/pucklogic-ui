"use client";

import { useState } from "react";
import type { RankedPlayer, Source } from "@/types";

type SortKey = "composite_rank" | "name" | "team" | "default_position" | "projected_fantasy_points";
type SortDir = "asc" | "desc";

interface Props {
  rankings: RankedPlayer[];
  sources: Source[];
}

function compare(a: RankedPlayer, b: RankedPlayer, key: SortKey, dir: SortDir): number {
  const av = a[key];
  const bv = b[key];
  const cmp =
    typeof av === "string"
      ? (av ?? "").localeCompare((bv as string | null) ?? "")
      : ((av ?? 0) as number) - ((bv ?? 0) as number);
  return dir === "asc" ? cmp : -cmp;
}

export function RankingsTable({ rankings, sources: _sources }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("composite_rank");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  if (rankings.length === 0) {
    return <p className="text-sm text-slate-500">No rankings computed yet.</p>;
  }

  const sorted = [...rankings].sort((a, b) => compare(a, b, sortKey, sortDir));

  function SortHeader({ colKey, label }: { colKey: SortKey; label: string }) {
    const active = sortKey === colKey;
    return (
      <th
        role="columnheader"
        onClick={() => handleSort(colKey)}
        className="cursor-pointer select-none px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 hover:text-slate-900"
      >
        {label}{active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
      </th>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead className="border-b border-slate-200 bg-slate-50">
          <tr>
            <SortHeader colKey="composite_rank" label="Rank" />
            <SortHeader colKey="name" label="Name" />
            <SortHeader colKey="team" label="Team" />
            <SortHeader colKey="default_position" label="Pos" />
            <SortHeader colKey="projected_fantasy_points" label="FanPts" />
            <th role="columnheader" className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">VORP</th>
            <th role="columnheader" className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">Sources</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((player) => (
            <tr key={player.player_id} className="hover:bg-slate-50">
              <td className="px-3 py-2 tabular-nums">{player.composite_rank}</td>
              <td className="px-3 py-2 font-medium">{player.name}</td>
              <td className="px-3 py-2">{player.team}</td>
              <td className="px-3 py-2">{player.default_position}</td>
              <td className="px-3 py-2 tabular-nums">{player.projected_fantasy_points?.toFixed(2) ?? "—"}</td>
              <td className="px-3 py-2 tabular-nums">{player.vorp?.toFixed(2) ?? "—"}</td>
              <td className="px-3 py-2 tabular-nums">{player.source_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
