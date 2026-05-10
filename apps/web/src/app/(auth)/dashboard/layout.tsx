export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex h-10 items-center gap-3 border-b border-border-subtle bg-bg-surface px-4">
        <button className="pl-btn-ghost flex items-center gap-1.5 rounded px-2 py-1 text-sm">
          <span className="text-text-secondary">Draft Kit</span>
          <svg
            className="h-3.5 w-3.5 text-text-tertiary"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>
        <div className="h-4 w-px bg-border-subtle" />
        <button className="pl-btn-ghost rounded px-2 py-1 text-sm text-text-secondary">
          League profile
        </button>
        <button className="pl-btn-ghost rounded px-2 py-1 text-sm text-text-secondary">
          Weights
        </button>
        <div className="ml-auto">
          <button className="pl-btn-primary flex items-center gap-1.5 rounded px-3 py-1 text-xs">
            ▶ Compute
          </button>
        </div>
      </div>
      <div className="flex flex-1 flex-col">{children}</div>
    </div>
  );
}
