import { KitContextSwitcher } from "@/components/KitContextSwitcher";
import { StartDraftButton } from "@/components/StartDraftButton";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex h-10 items-center gap-3 border-b border-border-subtle bg-bg-surface px-4">
        <KitContextSwitcher />
        <div className="h-4 w-px bg-border-subtle" />
        <button className="pl-btn-ghost rounded px-2 py-1 text-sm text-text-secondary">
          League profile
        </button>
        <button className="pl-btn-ghost rounded px-2 py-1 text-sm text-text-secondary">
          Weights
        </button>
        <div className="ml-auto">
          <StartDraftButton />
        </div>
      </div>
      <div className="flex flex-1 flex-col">{children}</div>
    </div>
  );
}
