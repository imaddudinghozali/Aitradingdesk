import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import { safeFetch } from "@/lib/api";
import type { ReplayRun } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ReplayPage() {
  const runs = await safeFetch<ReplayRun[]>("/replay?limit=50");
  return (
    <>
      <PageHeader
        title="Replay Candle Mentah"
        description="Engine re-evaluasi hypothetical. Candle diproses kronologis dan keputusan dibuat oleh policy pluggable dengan no-look-ahead ketat."
      />

      <Panel heading="Cara menjalankan" className="mb-4">
        <pre className="overflow-auto rounded bg-shadow-bg/40 p-3 font-mono text-[11px] text-shadow-muted">
{`POST /replay/run
{
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "start_utc": "2024-05-20T00:00:00Z",
  "end_utc":   "2024-05-21T00:00:00Z",
  "policy": "basic",
  "step_bars": 4,
  "horizon_bars": 24
}`}
        </pre>
        <p className="mt-2 text-xs text-shadow-muted">
          Policy <span className="font-mono text-shadow-ink">basic</span>{" "}
          memakai gate Daye Q2/Q3 + sweep-and-rejection + minimum RR. Policy
          custom bisa didaftarkan dengan implementasi{" "}
          <span className="font-mono">ReplayPolicy</span> di backend.
        </p>
      </Panel>

      {runs.error ? (
        <ErrorPanel message={runs.error} />
      ) : runs.data && runs.data.length ? (
        <Panel heading="Run Replay Terbaru">
          <table className="w-full text-left text-xs">
            <thead className="text-shadow-muted">
              <tr>
                <th className="px-2 py-1">Run</th>
                <th className="px-2 py-1">Symbol</th>
                <th className="px-2 py-1">TF</th>
                <th className="px-2 py-1">Policy</th>
                <th className="px-2 py-1">Window</th>
                <th className="px-2 py-1">Eval</th>
                <th className="px-2 py-1">Setup</th>
                <th className="px-2 py-1">No Trade</th>
                <th className="px-2 py-1">Win</th>
                <th className="px-2 py-1">Loss</th>
                <th className="px-2 py-1">Winrate</th>
                <th className="px-2 py-1">Avg RR</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {runs.data.map((r) => (
                <tr key={r.id} className="border-t border-shadow-border">
                  <td className="px-2 py-1">
                    <StatusPill value={r.status} />
                    <span className="ml-2 text-shadow-muted">#{r.id}</span>
                  </td>
                  <td className="px-2 py-1">{r.symbol}</td>
                  <td className="px-2 py-1">{r.timeframe}</td>
                  <td className="px-2 py-1">{r.policy_name}</td>
                  <td className="px-2 py-1 whitespace-nowrap text-shadow-muted">
                    {new Date(r.start_utc).toLocaleDateString()} -{" "}
                    {new Date(r.end_utc).toLocaleDateString()}
                  </td>
                  <td className="px-2 py-1">{r.evaluation_points}</td>
                  <td className="px-2 py-1">{r.valid_setups}</td>
                  <td className="px-2 py-1 text-shadow-muted">{r.no_trades}</td>
                  <td className="px-2 py-1 text-shadow-ok">{r.setup_wins}</td>
                  <td className="px-2 py-1 text-shadow-err">{r.setup_losses}</td>
                  <td className="px-2 py-1">{fmt(r.winrate)}</td>
                  <td className="px-2 py-1">{fmt(r.average_rr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      ) : (
        <EmptyState
          title="Belum ada run replay"
          description="POST /replay/run untuk grading skenario hypothetical dari candle tersimpan."
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
