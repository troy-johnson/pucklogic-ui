import { fetchSources } from "@/lib/api/sources";
import { PreDraftWorkspace } from "@/components/PreDraftWorkspace";

export default async function DashboardPage() {
  const sources = await fetchSources().catch(() => []);

  return <PreDraftWorkspace initialSources={sources} />;
}
