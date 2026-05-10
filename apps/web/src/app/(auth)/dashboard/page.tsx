import { loadInitialRankings } from "@/lib/rankings/load-initial";
import { PreDraftWorkspace } from "@/components/PreDraftWorkspace";

export default async function DashboardPage() {
  const { sources, rankings } = await loadInitialRankings();

  return (
    <PreDraftWorkspace
      initialSources={sources}
      initialRankings={rankings}
    />
  );
}
