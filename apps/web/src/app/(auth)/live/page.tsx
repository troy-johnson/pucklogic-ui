import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { fetchSyncState, type SyncStateResponse } from "@/lib/api/draft-sessions";
import { loadInitialRankings } from "@/lib/rankings/load-initial";
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

  let syncState: SyncStateResponse;
  try {
    syncState = await fetchSyncState(sessionId, token);
  } catch {
    // Stale or invalid sessionId — bounce back to dashboard.
    // Cookie cleanup happens client-side after the user reaches /dashboard
    // and triggers a new flow; the redirect prevents a broken /live render.
    redirect("/dashboard");
  }

  const { rankings } = await loadInitialRankings();

  return (
    <LiveDraftScreen
      players={rankings}
      myTeamPlayers={[]}
      initialSyncState={syncState}
    />
  );
}
