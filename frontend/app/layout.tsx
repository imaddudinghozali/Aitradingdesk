import "./globals.css";
import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import { apiBaseUrl } from "@/lib/api";

export const metadata: Metadata = {
  title: "Imadztrades Shadow AI Trading Desk",
  description:
    "Dashboard intelligence trading XAUUSD shadow-style dengan narrative DOL-first.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-x-auto">
            <div className="border-b border-shadow-border bg-shadow-panel px-6 py-3 text-xs text-shadow-muted">
              Backend: <span className="font-mono text-shadow-ink">{apiBaseUrl()}</span>
            </div>
            <div className="p-6">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
