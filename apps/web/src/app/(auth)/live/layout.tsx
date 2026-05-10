import { ReconnectBanner } from "@/components/ReconnectBanner";

export default function LiveLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <ReconnectBanner />
      {children}
    </div>
  );
}
