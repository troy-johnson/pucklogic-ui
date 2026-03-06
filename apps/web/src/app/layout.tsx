import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PuckLogic Draft Kit",
  description: "AI-powered fantasy hockey draft rankings and draft monitor",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
