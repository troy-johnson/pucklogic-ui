/**
 * Validates a `next` redirect target so we never bounce a user onto an
 * external host or a protocol-relative URL crafted via open-redirect.
 *
 * Safe values:
 *   - Start with a single `/`
 *   - Are not protocol-relative (`//evil.com`, `/\evil.com`)
 *
 * Anything else falls back to `/dashboard`.
 */
export function safeNextPath(raw: string | null | undefined, fallback = "/dashboard"): string {
  if (!raw) return fallback;
  if (!raw.startsWith("/")) return fallback;
  if (raw.startsWith("//") || raw.startsWith("/\\")) return fallback;
  return raw;
}
