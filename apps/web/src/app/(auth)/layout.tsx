import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { apiFetch } from "@/lib/api";
import AppShell from "@/components/AppShell";
import { UserProvider } from "@/components/UserProvider";

interface EntitlementsResult {
  kit_pass: boolean;
  draft_passes: number;
}

export default async function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const {
    data: { session },
  } = await supabase.auth.getSession();

  let passBalance = 0;
  if (session?.access_token) {
    try {
      const entitlements = await apiFetch<EntitlementsResult>("/entitlements", {
        token: session.access_token,
      });
      passBalance = entitlements.draft_passes;
    } catch (err) {
      // Surface failures in server logs so degraded "0 passes" state can be
      // distinguished from genuine zero-balance accounts during incidents.
      console.error("[auth-layout] entitlements fetch failed:", err);
    }
  }

  return (
    <UserProvider initialUser={user}>
      <AppShell passBalance={passBalance}>{children}</AppShell>
    </UserProvider>
  );
}
