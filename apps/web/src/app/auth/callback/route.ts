import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { safeNextPath } from "@/lib/safe-next";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const nextPath = safeNextPath(searchParams.get("next"));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      return NextResponse.redirect(new URL(nextPath, request.url));
    }

    // Log to server-side console so the failure shows up in deploy logs;
    // mirrors the entitlements-failure logging in (auth)/layout.tsx.
    console.error("[auth-callback] exchangeCodeForSession failed:", error);
  } else {
    console.error("[auth-callback] missing `code` query param");
  }

  return NextResponse.redirect(
    new URL("/login?error=auth_callback_failed", request.url),
  );
}
