"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/store";
import { ManualPickDrawer } from "./ManualPickDrawer";
import { clearDraftSessionCookie } from "@/lib/draft-session-cookie";
import type { SyncStateResponse } from "@/lib/api/draft-sessions";
import type { DraftMode } from "@/store/slices/draftSession";
import type { DraftPick, RankedPlayer } from "@/types";

const POSITIONS = ["All", "C", "LW", "RW", "D", "G"] as const;
type Position = (typeof POSITIONS)[number];

const ROSTER_NEEDS: Record<string, { filled: number; needed: number }> = {
  C: { filled: 0, needed: 2 },
  LW: { filled: 0, needed: 2 },
  RW: { filled: 0, needed: 2 },
  D: { filled: 0, needed: 4 },
  G: { filled: 0, needed: 2 },
};

interface Props {
  players: RankedPlayer[];
  myTeamPlayers: RankedPlayer[];
  initialSyncState?: SyncStateResponse;
}

export function LiveDraftScreen({
  players,
  myTeamPlayers: _myTeamPlayers,
  initialSyncState,
}: Props) {
  const router = useRouter();
  const { picks, mode, sessionId, setMode, recordPick, hydrateSession, endSession } = useStore();
  const [activePosition, setActivePosition] = useState<Position>("All");
  const [drawerOpen, setDrawerOpen] = useState(false);

  function handleEndDraft() {
    if (!confirm("End this draft session? Picks will be saved.")) return;
    endSession();
    clearDraftSessionCookie();
    router.push("/dashboard");
  }

  useEffect(() => {
    if (initialSyncState && sessionId !== initialSyncState.session_id) {
      hydrateSession({
        sessionId: initialSyncState.session_id,
        kitId: initialSyncState.kit_id,
        picks: initialSyncState.picks.map((p) => ({
          playerId: p.player_id,
          playerName: p.player_name,
          round: p.round,
          pickNumber: p.pick_number,
          recordedAt: p.recorded_at,
        })),
        mode: initialSyncState.mode as DraftMode,
      });
    }
  }, [initialSyncState, sessionId, hydrateSession]);

  const pickedIds = new Set(picks.map((p: DraftPick) => p.playerId));

  const available = players.filter((p) => !pickedIds.has(p.player_id));
  const filtered =
    activePosition === "All"
      ? available
      : available.filter(
          (p) =>
            p.default_position === activePosition ||
            p.platform_positions.includes(activePosition),
        );

  const [priority, alt, sleeper] = filtered;

  const currentRound = Math.floor(picks.length / 10) + 1;
  const currentPick = (picks.length % 10) + 1;

  function handleConfirmPick(pick: {
    playerId: string;
    round: number;
    pickNumber: number;
  }) {
    const player = players.find((p) => p.player_id === pick.playerId);
    recordPick({
      playerId: pick.playerId,
      playerName: player?.name ?? pick.playerId,
      round: pick.round,
      pickNumber: pick.pickNumber,
      recordedAt: new Date().toISOString(),
    });
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left — available players */}
      <div className="flex flex-1 flex-col overflow-auto">
        <div className="sticky top-0 z-10 border-b border-border-subtle bg-bg-surface px-4 py-3">
          <h2 className="mb-2 text-sm font-semibold">Available players</h2>
          <div className="flex gap-1.5">
            {POSITIONS.map((pos) => (
              <button
                key={pos}
                className="pl-pill rounded-pill px-2.5 py-0.5 text-xs"
                data-active={activePosition === pos}
                onClick={() => setActivePosition(pos)}
              >
                {pos}
              </button>
            ))}
          </div>
        </div>

        <div className="divide-y divide-border-subtle">
          {filtered.map((player) => (
            <div
              key={player.player_id}
              className="flex items-center justify-between px-4 py-2.5"
            >
              <div>
                <span className="text-sm font-medium">{player.name}</span>
                <span className="ml-2 text-xs text-text-secondary">
                  {player.default_position} · {player.team}
                </span>
              </div>
              <span className="text-xs font-medium text-accent-blue">
                #{player.composite_rank}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <aside className="flex w-72 flex-col gap-4 border-l border-border-subtle bg-bg-surface p-4">
        {/* Suggestion cards */}
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            Suggestions
          </h3>
          <div className="space-y-2">
            {[
              { label: "Priority pick", player: priority },
              { label: "Alt pick", player: alt },
              { label: "Sleeper", player: sleeper },
            ].map(({ label, player }) => (
              <div
                key={label}
                className="pl-card rounded-lg p-3"
              >
                <p className="text-[10px] font-semibold uppercase tracking-wide text-text-tertiary">
                  {label}
                </p>
                {player ? (
                  <>
                    <p className="text-sm font-medium">{player.name}</p>
                    <p className="text-xs text-text-secondary">
                      {player.default_position} · {player.team}
                    </p>
                  </>
                ) : (
                  <p className="text-xs text-text-secondary">—</p>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Roster needs */}
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            Roster needs
          </h3>
          <div className="grid grid-cols-5 gap-1">
            {Object.entries(ROSTER_NEEDS).map(([pos, { filled, needed }]) => (
              <div key={pos} className="flex flex-col items-center">
                <span className="text-[10px] text-text-tertiary">{pos}</span>
                <span
                  className={`text-xs font-semibold ${filled >= needed ? "text-color-success" : "text-color-warning"}`}
                >
                  {filled}/{needed}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* My team picks */}
        {picks.length > 0 && (
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
              My picks
            </h3>
            <div className="space-y-1">
              {picks.map((pick: DraftPick) => (
                <div key={pick.pickNumber} className="flex justify-between text-xs">
                  <span>{pick.playerName}</span>
                  <span className="text-text-secondary">
                    R{pick.round}.{pick.pickNumber}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Sync status */}
        <div
          data-testid="sync-status"
          className="mt-auto rounded-lg border border-border-subtle p-3"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-text-secondary">
              {mode === "sync"
                ? "Syncing via extension"
                : mode === "manual"
                  ? "Manual mode"
                  : "Reconnecting…"}
            </span>
            <span
              className={`h-2 w-2 rounded-full ${mode === "sync" ? "bg-color-success" : "bg-color-warning"}`}
            />
          </div>
          <button
            onClick={() => setDrawerOpen(true)}
            className="pl-btn-secondary w-full rounded py-1.5 text-xs"
          >
            + Manual pick
          </button>
          {mode === "sync" && (
            <button
              onClick={() => setMode("manual")}
              className="mt-1.5 w-full rounded py-1 text-xs text-text-tertiary hover:text-text-secondary"
            >
              Switch to manual
            </button>
          )}
          <button
            onClick={handleEndDraft}
            className="mt-1.5 w-full rounded py-1 text-xs text-color-error hover:bg-color-error/10"
          >
            End draft
          </button>
        </div>

        {sessionId === null && (
          <p className="text-xs text-color-error">No active session</p>
        )}
      </aside>

      <ManualPickDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onConfirm={handleConfirmPick}
        players={available}
        currentRound={currentRound}
        currentPick={currentPick}
      />
    </div>
  );
}
