import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { fetchSyncState } from "@/lib/api/draft-sessions";
import { fetchSources } from "@/lib/api/sources";
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

  const [syncState, sources] = await Promise.allSettled([
    fetchSyncState(sessionId, token),
    fetchSources(),
  ]);

  const players =
    syncState.status === "fulfilled" ? [] : [];
  void sources;

  return <LiveDraftScreen players={players} myTeamPlayers={[]} />;
}
