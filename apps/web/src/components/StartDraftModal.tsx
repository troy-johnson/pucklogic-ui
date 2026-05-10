"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createSession } from "@/lib/api/draft-sessions";
import { createClient } from "@/lib/supabase/client";
import { useStore } from "@/store";

export function StartDraftModal({
  kitId,
  onClose,
}: {
  kitId: string;
  onClose: () => void;
}) {
  const router = useRouter();
  const { startSession } = useStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setLoading(true);
    setError(null);

    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token ?? "";

      const response = await createSession({ kitId }, token);

      document.cookie = `draft-session-id=${response.session_id}; path=/; SameSite=Lax`;

      startSession({ sessionId: response.session_id, kitId });

      router.push("/live");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start draft");
      setLoading(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Start live draft"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      {/* Scrim */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="pl-card relative z-10 w-full max-w-sm rounded-xl p-6 shadow-modal">
        <h2 className="mb-2 text-lg font-semibold">Start live draft?</h2>
        <p className="mb-6 text-sm text-text-secondary">
          This will consume one draft pass from your kit and begin the live
          monitoring session.
        </p>

        {error && (
          <p role="alert" className="mb-4 rounded bg-color-error/10 px-3 py-2 text-sm text-color-error">
            {error}
          </p>
        )}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="pl-btn-secondary flex-1 rounded-md py-2 text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={loading}
            className="pl-btn-primary flex-1 rounded-md py-2 text-sm font-semibold"
          >
            {loading ? "Starting…" : "Start draft"}
          </button>
        </div>
      </div>
    </div>
  );
}
