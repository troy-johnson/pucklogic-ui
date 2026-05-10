import type { ReactNode } from "react";
import { UserMenuButton } from "./UserMenuButton";

export default function AppShell({
  passBalance,
  children,
}: {
  passBalance: number;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-bg-base">
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border-subtle bg-bg-surface/80 px-4 backdrop-blur-md">
        <span className="text-base font-semibold tracking-tight text-text-primary">
          PuckLogic
        </span>
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-text-secondary">
            {passBalance} passes
          </span>
          <UserMenuButton />
        </div>
      </header>
      <div className="flex flex-1 flex-col">{children}</div>
    </div>
  );
}
