import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import { safeFetch } from "@/lib/api";
import type { BacktestRun } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function BacktestPage() {
  const runs = await safeFetch<BacktestRun[]>("/backtests?limit=50");
  return (
    <>
      <PageHeader
        title="Backtest"
        description="Scoring walk-forward dari keputusan narrative yang sudah terekam. Pakai Replay untuk skenario hypothetical raw-candle."
      />
      {runs.error ? (
        <ErrorPanel message={runs.error} />
      ) : runs.data && runs.data.length ? (
        <Panel>
          <table className="w-full text-left text-xs">
            <thead className="text-shadow-muted">
              <tr>
                <th className="px-2 py-1">Run</th>
                <th className="px-2 py-1">Symbol</th>
                <th className="px-2 py-1">TF</th>
                <th className="px-2 py-1">Setup</th>
                <th className="px-2 py-1">Win</th>
                <th className="px-2 py-1">Loss</th>
                <th className="px-2 py-1">Winrate</th>
                <th className="px-2 py-1">Avg RR</th>
                <th className="px-2 py-1">MaxDD</th>
                <th className="px-2 py-1">Akurasi No-Trade</th>
                <th className="px-2 py-1">Best Q</th>
                <th className="px-2 py-1">Dibuat</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {runs.data.map((run) => (
                <tr key={run.id} className="border-t border-shadow-border">
                  <td className="px-2 py-1">
                    <StatusPill value={run.status} />
                    <span className="ml-2 text-shadow-muted">#{run.id}</span>
                  </td>
                  <td className="px-2 py-1">{run.symbol}</td>
                  <td className="px-2 py-1">{run.timeframe}</td>
                  <td className="px-2 py-1">{run.valid_setup_samples}</td>
                  <td className="px-2 py-1 text-shadow-ok">{run.setup_wins}</td>
                  <td className="px-2 py-1 text-shadow-err">{run.setup_losses}</td>
                  <td className="px-2 py-1">{fmt(run.winrate)}</td>
                  <td className="px-2 py-1">{fmt(run.average_rr)}</td>
                  <td className="px-2 py-1">{fmt(run.max_drawdown_rr)}</td>
                  <td className="px-2 py-1">{fmt(run.no_trade_accuracy)}</td>
                  <td className="px-2 py-1">{run.best_quarter ?? "-"}</td>
                  <td className="px-2 py-1 whitespace-nowrap">
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      ) : (
        <EmptyState
          title="Belum ada run backtest"
          description="POST /backtests/run untuk scoring keputusan narrative yang tersimpan."
        />
      )}
    </>
  );
}

function fmt(v: string | null | undefined): string {
  if (v == null) return "-";
  const num = Number(v);
  if (Number.isNaN(num)) return v;
  return num.toFixed(3);
}
