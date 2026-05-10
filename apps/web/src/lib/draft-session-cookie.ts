/**
 * Client-side `draft-session-id` cookie helpers.
 *
 * The cookie is read server-side by `app/(auth)/live/page.tsx` to hydrate
 * the live draft route. It is written here on session start and cleared
 * on session end.
 *
 * Cannot be HttpOnly — it must be JS-writable from the start-draft flow.
 * `Secure` is set conditionally so dev (http://localhost) still works.
 */

const COOKIE_NAME = "draft-session-id";
const MAX_AGE_SECONDS = 60 * 60 * 24; // 24 hours — typical draft window

function isSecureContext(): boolean {
  if (typeof window === "undefined") return false;
  return window.location.protocol === "https:";
}

export function writeDraftSessionCookie(sessionId: string): void {
  const parts = [
    `${COOKIE_NAME}=${encodeURIComponent(sessionId)}`,
    "path=/",
    "SameSite=Lax",
    `Max-Age=${MAX_AGE_SECONDS}`,
  ];
  if (isSecureContext()) parts.push("Secure");
  document.cookie = parts.join("; ");
}

export function clearDraftSessionCookie(): void {
  const parts = [
    `${COOKIE_NAME}=`,
    "path=/",
    "SameSite=Lax",
    "Max-Age=0",
  ];
  if (isSecureContext()) parts.push("Secure");
  document.cookie = parts.join("; ");
}
