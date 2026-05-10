"use client";

import { useMemo, useState } from "react";
import type { RankedPlayer } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: (pick: {
    playerId: string;
    round: number;
    pickNumber: number;
  }) => void;
  players: RankedPlayer[];
  currentRound: number;
  currentPick: number;
}

export function ManualPickDrawer({
  open,
  onClose,
  onConfirm,
  players,
  currentRound,
  currentPick,
}: Props) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [recorded, setRecorded] = useState(false);
  const [round, setRound] = useState(currentRound);
  const [pick, setPick] = useState(currentPick);

  const filtered = useMemo(() => {
    if (!query) return players;
    const q = query.toLowerCase();
    return players.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.team ?? "").toLowerCase().includes(q),
    );
  }, [players, query]);

  function handleConfirm() {
    if (!selectedId) return;
    onConfirm({ playerId: selectedId, round, pickNumber: pick });
    setRecorded(true);
    setTimeout(() => {
      setRecorded(false);
      setSelectedId(null);
      setQuery("");
      onClose();
    }, 700);
  }

  if (!open) return null;

  return (
    <>
      <div
        className="pl-scrim fixed inset-0 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="pl-drawer-enter fixed right-0 top-0 z-50 flex h-full w-80 flex-col bg-bg-elevated shadow-drawer">
        <div className="flex h-14 items-center justify-between border-b border-border-subtle px-4">
          <h2 className="text-sm font-semibold">Record manual pick</h2>
          <button
            aria-label="Close"
            onClick={onClose}
            className="pl-btn-ghost rounded p-1.5"
          >
            ✕
          </button>
        </div>

        <div className="flex gap-3 border-b border-border-subtle p-4">
          <label className="flex flex-col gap-1 text-xs text-text-secondary">
            Round
            <input
              type="number"
              min={1}
              value={round}
              onChange={(e) => setRound(Number(e.target.value))}
              className="pl-input w-16 rounded px-2 py-1 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-text-secondary">
            Pick
            <input
              type="number"
              min={1}
              value={pick}
              onChange={(e) => setPick(Number(e.target.value))}
              className="pl-input w-16 rounded px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div className="border-b border-border-subtle p-3">
          <input
            role="searchbox"
            type="search"
            placeholder="Search players…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-input w-full rounded px-3 py-1.5 text-sm"
          />
        </div>

        <div className="flex-1 overflow-y-auto">
          {filtered.map((player) => (
            <button
              key={player.player_id}
              onClick={() => setSelectedId(player.player_id)}
              className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-bg-overlay ${
                selectedId === player.player_id
                  ? "bg-accent-blue-dim text-accent-blue"
                  : ""
              }`}
            >
              <span>{player.name}</span>
              <span className="text-xs text-text-secondary">
                {player.default_position} · {player.team}
              </span>
            </button>
          ))}
        </div>

        <div className="border-t border-border-subtle p-3">
          {recorded ? (
            <div className="rounded bg-color-success/10 px-4 py-2 text-center text-sm font-medium text-color-success">
              Recorded
            </div>
          ) : (
            <button
              disabled={!selectedId}
              onClick={handleConfirm}
              className="pl-btn-primary w-full rounded-md py-2 text-sm font-semibold disabled:opacity-40"
            >
              Confirm pick
            </button>
          )}
        </div>
      </div>
    </>
  );
}
