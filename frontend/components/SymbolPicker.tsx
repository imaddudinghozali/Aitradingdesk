"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";

const SYMBOLS = ["XAUUSD", "XAGUSD"];

export default function SymbolPicker({
  defaultSymbol,
}: {
  defaultSymbol: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const current = params?.get("symbol") || defaultSymbol;

  return (
    <select
      value={current}
      onChange={(e) => {
        const next = new URLSearchParams(params?.toString());
        next.set("symbol", e.target.value);
        router.replace(`${pathname}?${next.toString()}`);
      }}
      className="rounded border border-shadow-border bg-shadow-bg px-2 py-1 text-xs text-shadow-ink"
    >
      {SYMBOLS.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  );
}
