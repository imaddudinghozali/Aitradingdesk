import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import IngestControls from "./IngestControls";
import { safeFetch } from "@/lib/api";
import type { IngestionRun, SchedulerStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function MarketIngestPage() {
  const [runs, status] = await Promise.all([
    safeFetch<IngestionRun[]>("/market/ingest/runs?limit=50"),
    safeFetch<SchedulerStatus>("/market/ingest/scheduler/status"),
  ]);

  return (
    <>
      <PageHeader
        title="Market Ingest"
        description="Pluggable live market data adapter — TwelveData by default. Audit log + scheduler controls."
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Panel
          heading="Scheduler"
          actions={
            status.data ? (
              <StatusPill value={status.data.running ? "running" : "stopped"} />
            ) : null
          }
        >
          {status.error ? (
            <div className="text-xs text-shadow-muted">{status.error}</div>
          ) : status.data ? (
            <div className="kv">
              <div className="text-shadow-muted">Provider</div>
              <span className="font-mono">
                {status.data.provider ?? "not configured"}
              </span>
              <div className="text-shadow-muted">Symbols</div>
              <span className="font-mono">
                {status.data.symbols.join(", ") || "—"}
              </span>
              <div className="text-shadow-muted">Timeframes</div>
              <span className="font-mono">
                {status.data.timeframes.join(", ") || "—"}
              </span>
              <div className="text-shadow-muted">Interval</div>
              <span className="font-mono">
                {status.data.interval_seconds
                  ? `${status.data.interval_seconds}s`
                  : "—"}
              </span>
              <div className="text-shadow-muted">Last tick</div>
              <span className="font-mono text-xs">
                {status.data.last_tick_utc
                  ? new Date(status.data.last_tick_utc).toLocaleString()
                  : "—"}
              </span>
              <div className="text-shadow-muted">Next tick</div>
              <span className="font-mono text-xs">
                {status.data.next_tick_utc
                  ? new Date(status.data.next_tick_utc).toLocaleString()
                  : "—"}
              </span>
              {status.data.last_error && (
                <>
                  <div className="text-shadow-muted">Last error</div>
                  <span className="text-xs text-shadow-err">
                    {status.data.last_error}
                  </span>
                </>
              )}
            </div>
          ) : (
            <EmptyState title="Scheduler status unavailable" />
          )}
        </Panel>

        <Panel heading="Controls">
          <IngestControls />
        </Panel>
      </div>

      <Panel heading="Recent Ingestion Runs" className="mt-4">
        {runs.error ? (
          <ErrorPanel message={runs.error} />
        ) : runs.data && runs.data.length ? (
          <table className="w-full text-left text-xs">
            <thead className="text-shadow-muted">
              <tr>
                <th className="px-2 py-1">Started</th>
                <th className="px-2 py-1">Provider</th>
                <th className="px-2 py-1">Symbol</th>
                <th className="px-2 py-1">TF</th>
                <th className="px-2 py-1">Status</th>
                <th className="px-2 py-1">Fetched</th>
                <th className="px-2 py-1">Inserted</th>
                <th className="px-2 py-1">Skipped</th>
                <th className="px-2 py-1">Error</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {runs.data.map((r, i) => (
                <tr key={i} className="border-t border-shadow-border">
                  <td className="px-2 py-1 whitespace-nowrap">
                    {new Date(r.started_at_utc).toLocaleString()}
                  </td>
                  <td className="px-2 py-1">{r.provider}</td>
                  <td className="px-2 py-1">{r.symbol}</td>
                  <td className="px-2 py-1">{r.timeframe}</td>
                  <td className="px-2 py-1">
                    <StatusPill value={r.status} />
                  </td>
                  <td className="px-2 py-1">{r.candles_fetched}</td>
                  <td className="px-2 py-1 text-shadow-ok">
                    {r.candles_inserted}
                  </td>
                  <td className="px-2 py-1 text-shadow-muted">
                    {r.candles_skipped}
                  </td>
                  <td className="px-2 py-1 text-shadow-err">
                    {r.error_message ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState
            title="No ingestion runs yet"
            description="POST /market/ingest/run with symbols + timeframes (or set defaults in .env)."
          />
        )}
      </Panel>
    </>
  );
}
