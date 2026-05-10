import { createClient } from "@/lib/supabase/server";
import { loadInitialRankings } from "@/lib/rankings/load-initial";
import { PreDraftWorkspace } from "@/components/PreDraftWorkspace";

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;

  const { sources, rankings } = await loadInitialRankings(token);

  return (
    <PreDraftWorkspace
      initialSources={sources}
      initialRankings={rankings}
    />
  );
}
