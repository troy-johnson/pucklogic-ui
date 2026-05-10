"use client";

import { useEffect, useState } from "react";
import { KitSwitcher } from "./KitSwitcher";
import { listKits } from "@/lib/api/user-kits";
import { createClient } from "@/lib/supabase/client";
import { useStore } from "@/store";

export function KitContextSwitcher() {
  const kits = useStore((s) => s.kits);
  const activeKitId = useStore((s) => s.activeKitId);
  const setKits = useStore((s) => s.setKits);
  const setActiveKit = useStore((s) => s.setActiveKit);
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const supabase = createClient();
        const { data } = await supabase.auth.getSession();
        const token = data.session?.access_token;
        if (!token) return;
        const fetched = await listKits(token);
        if (cancelled) return;
        setKits(fetched);
        if (fetched.length > 0 && !activeKitId) {
          setActiveKit(fetched[0].id);
        }
      } catch (err) {
        console.error("[kit-context-switcher] failed to load kits:", err);
      } finally {
        if (!cancelled) setLoaded(true);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeKit = kits.find((k) => k.id === activeKitId);
  const label = activeKit?.name ?? (loaded ? "Select a kit" : "Draft Kit");

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="pl-btn-ghost flex items-center gap-1.5 rounded px-2 py-1 text-sm"
      >
        <span className="text-text-secondary">{label}</span>
        <svg
          className="h-3.5 w-3.5 text-text-tertiary"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      <KitSwitcher open={open} onClose={() => setOpen(false)} />
    </>
  );
}
