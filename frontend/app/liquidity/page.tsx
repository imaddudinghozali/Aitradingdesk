import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import SymbolPicker from "@/components/SymbolPicker";
import LiquidityChart from "@/components/LiquidityChart";
import { DEFAULT_SYMBOL, safeFetch } from "@/lib/api";
import { idText } from "@/lib/i18n";
import type { LiquidityLevel, MarketSnapshot } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function LiquidityMapPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string }>;
}) {
  const params = await searchParams;
  const symbol = (params.symbol || DEFAULT_SYMBOL).toUpperCase();
  const [levels, snapshots] = await Promise.all([
    safeFetch<LiquidityLevel[]>(`/liquidity/levels?symbol=${symbol}`),
    safeFetch<MarketSnapshot[]>(
      `/market/snapshots?symbol=${symbol}&timeframe=H1&limit=200`,
    ),
  ]);

  return (
    <>
      <PageHeader
        title="Peta Likuiditas"
        description="Level likuiditas aktif diplot terhadap candle H1. BSL = biru, SSL = amber; level taken tampil dashed."
        actions={<SymbolPicker defaultSymbol={DEFAULT_SYMBOL} />}
      />

      {snapshots.error && !snapshots.error.startsWith("404") && (
        <ErrorPanel message={snapshots.error} />
      )}

      {snapshots.data && snapshots.data.length > 0 ? (
        <Panel heading={`${symbol} H1 dengan overlay likuiditas`}>
          <LiquidityChart
            snapshots={snapshots.data}
            levels={levels.data ?? []}
          />
        </Panel>
      ) : (
        <EmptyState
          title="Belum ada candle H1 tersimpan"
          description="Jalankan /market/ingest atau POST /market/ohlc untuk mengisi history H1."
        />
      )}

      <Panel className="mt-4" heading="Level Likuiditas">
        {levels.error ? (
          <div className="text-xs text-shadow-muted">{levels.error}</div>
        ) : levels.data && levels.data.length ? (
          <table className="w-full text-left text-xs">
            <thead className="text-shadow-muted">
              <tr>
                <th className="px-2 py-1">Tipe</th>
                <th className="px-2 py-1">Side</th>
                <th className="px-2 py-1">Harga</th>
                <th className="px-2 py-1">Status</th>
                <th className="px-2 py-1">TF</th>
                <th className="px-2 py-1">Alasan</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {levels.data.map((l) => (
                <tr key={l.id} className="border-t border-shadow-border">
                  <td className="px-2 py-1">{l.level_type}</td>
                  <td className="px-2 py-1">{l.liquidity_side}</td>
                  <td className="px-2 py-1">{l.price}</td>
                  <td className="px-2 py-1">
                    <StatusPill value={l.status} />
                  </td>
                  <td className="px-2 py-1">{l.source_timeframe}</td>
                  <td className="px-2 py-1 font-sans text-shadow-muted">
                    {idText(l.status_reason)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="Belum ada level likuiditas" />
        )}
      </Panel>
    </>
  );
}
