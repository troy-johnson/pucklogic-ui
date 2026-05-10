"use client";

import { useState } from "react";
import { StartDraftModal } from "./StartDraftModal";
import { useStore } from "@/store";

export function StartDraftButton() {
  const activeKitId = useStore((s) => s.activeKitId);
  const [open, setOpen] = useState(false);

  const disabled = !activeKitId;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        disabled={disabled}
        title={disabled ? "Select a kit first" : "Start a live draft"}
        className="pl-btn-primary flex items-center gap-1.5 rounded px-3 py-1 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
      >
        ▶ Start draft
      </button>

      {open && activeKitId && (
        <StartDraftModal kitId={activeKitId} onClose={() => setOpen(false)} />
      )}
    </>
  );
}
