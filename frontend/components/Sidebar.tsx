"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS: { heading: string; items: { href: string; label: string }[] }[] =
  [
    {
      heading: "Narrative",
      items: [
        { href: "/", label: "Board Narrative Aktif" },
        { href: "/dol", label: "DOL Status" },
        { href: "/direction-liquidity", label: "IRL / ERL Mapping" },
        { href: "/session-quarter", label: "Sesi & Quarter" },
        { href: "/ssmt", label: "SSMT XAU/XAG" },
      ],
    },
    {
      heading: "Market",
      items: [
        { href: "/liquidity", label: "Peta Likuiditas" },
        { href: "/market-ingest", label: "Ingest Market" },
        { href: "/calendar", label: "Kalender Ekonomi" },
      ],
    },
    {
      heading: "Review",
      items: [
        { href: "/alerts", label: "Riwayat Alert" },
        { href: "/journal", label: "Journal" },
        { href: "/backtest", label: "Backtest" },
        { href: "/replay", label: "Replay Candle Mentah" },
      ],
    },
  ];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-64 shrink-0 border-r border-shadow-border bg-shadow-panel">
      <div className="border-b border-shadow-border px-5 py-4">
        <div className="text-sm font-semibold text-shadow-accent">
          Imadztrade&apos;s
        </div>
        <div className="text-xs text-shadow-muted">
          Meja Trading Shadow AI
        </div>
      </div>
      <nav className="px-3 py-4 space-y-6">
        {SECTIONS.map((section) => (
          <div key={section.heading}>
            <div className="px-2 pb-2 text-[10px] uppercase tracking-wider text-shadow-muted">
              {section.heading}
            </div>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active =
                  pathname === item.href ||
                  (item.href !== "/" && pathname?.startsWith(item.href));
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={
                        "block rounded px-2 py-1.5 text-sm transition-colors " +
                        (active
                          ? "bg-shadow-accent/10 text-shadow-accent"
                          : "text-shadow-ink hover:bg-shadow-border/50")
                      }
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
