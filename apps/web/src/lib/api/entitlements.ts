import { apiFetch } from "./index";

export interface EntitlementsResult {
  kit_pass: boolean;
  draft_passes: number;
}

export async function fetchEntitlements(
  token: string,
): Promise<EntitlementsResult> {
  return apiFetch<EntitlementsResult>("/entitlements", { token });
}
