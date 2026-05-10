"use client";

import { useStore } from "@/store";

export function ReconnectBanner() {
  const { mode, setMode } = useStore();

  if (mode !== "reconnecting" && mode !== "disconnected") return null;

  const isDisconnected = mode === "disconnected";

  return (
    <div
      role="alert"
      className="flex items-center justify-between gap-4 bg-color-warning/10 px-4 py-2.5 text-sm"
      style={{ animation: "pl-fade-in 220ms ease forwards" }}
    >
      <span className="font-medium text-color-warning">
        {isDisconnected
          ? "Extension disconnected — picks won't sync automatically"
          : "Reconnecting to draft monitor…"}
      </span>
      <button
        onClick={() => setMode("manual")}
        className="whitespace-nowrap rounded border border-color-warning/30 px-3 py-1 text-xs font-medium text-color-warning hover:bg-color-warning/10 transition-colors"
      >
        Switch to manual
      </button>
    </div>
  );
}
