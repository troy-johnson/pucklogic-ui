import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { fetchSyncState, type SyncStateResponse } from "@/lib/api/draft-sessions";
import { LiveDraftScreen } from "@/components/LiveDraftScreen";

export default async function LivePage() {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get("draft-session-id")?.value;

  if (!sessionId) {
    redirect("/dashboard");
  }

  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";

  let syncState: SyncStateResponse | undefined;
  try {
    syncState = await fetchSyncState(sessionId, token);
  } catch {
    // Stale or invalid sessionId — bounce back to dashboard.
    // The cookie cleanup happens client-side; the redirect prevents
    // a broken /live render in the meantime.
    redirect("/dashboard");
  }

  // Ranked players come from a separate compute call gated on user
  // scoring config / platform — wired in a follow-up. For now LiveDraftScreen
  // renders with no available players but full session-state hydration.
  return (
    <LiveDraftScreen
      players={[]}
      myTeamPlayers={[]}
      initialSyncState={syncState}
    />
  );
}
