"use client";

import { useUser } from "./UserProvider";

export function UserMenuButton() {
  const user = useUser();

  return (
    <button
      aria-label="User menu"
      className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-bg-raised hover:text-text-primary transition-colors"
    >
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-accent-blue-dim text-xs font-semibold text-accent-blue">
        {user?.email?.[0]?.toUpperCase() ?? "?"}
      </span>
      <span className="hidden sm:inline">{user?.email ?? "Account"}</span>
    </button>
  );
}
