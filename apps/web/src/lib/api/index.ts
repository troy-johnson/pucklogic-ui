/**
 * API client for the PuckLogic FastAPI backend.
 *
 * All data reads and writes must go through this module — never call Supabase
 * directly for data. The Supabase client (lib/supabase/) is auth-only.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiFetchOptions = RequestInit & { token?: string };

function buildJsonRequestOptions(options: ApiFetchOptions): RequestInit {
  const { token, ...fetchOptions } = options;

  return {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...fetchOptions.headers,
    },
  };
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, buildJsonRequestOptions(options));

  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }

  // 204 No Content / 205 Reset Content — no body to parse
  if (res.status === 204 || res.status === 205) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export async function apiFetchBinary(
  path: string,
  options: ApiFetchOptions = {},
): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, buildJsonRequestOptions(options));

  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }

  return res;
}
