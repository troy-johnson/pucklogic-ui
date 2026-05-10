import type { CreateUserKitRequest, UserKit } from "@/types";
import { apiFetch } from "./index";

// ── Legacy unauthenticated exports (preserved for backwards compat) ─────────

export async function fetchUserKits(): Promise<UserKit[]> {
  return apiFetch<UserKit[]>("/user-kits");
}

export async function createUserKit(req: CreateUserKitRequest): Promise<UserKit> {
  return apiFetch<UserKit>("/user-kits", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function deleteUserKit(id: string): Promise<void> {
  return apiFetch<void>(`/user-kits/${id}`, { method: "DELETE" });
}

// ── Token-authenticated exports (used by Wave 3+ components) ────────────────

export async function listKits(token: string): Promise<UserKit[]> {
  return apiFetch<UserKit[]>("/user-kits", { token });
}

export async function createKit(
  payload: CreateUserKitRequest,
  token: string,
): Promise<UserKit> {
  return apiFetch<UserKit>("/user-kits", {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export async function updateKit(
  id: string,
  patch: Partial<Pick<UserKit, "name" | "source_weights">>,
  token: string,
): Promise<UserKit> {
  return apiFetch<UserKit>(`/user-kits/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
    token,
  });
}

export async function deleteKit(id: string, token: string): Promise<void> {
  return apiFetch<void>(`/user-kits/${id}`, { method: "DELETE", token });
}

export async function duplicateKit(id: string, token: string): Promise<UserKit> {
  return apiFetch<UserKit>(`/user-kits/${id}/duplicate`, {
    method: "POST",
    token,
  });
}
