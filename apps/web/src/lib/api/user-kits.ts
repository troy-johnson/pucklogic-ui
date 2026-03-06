import type { CreateUserKitRequest, UserKit } from "@/types";
import { apiFetch } from "./index";

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
