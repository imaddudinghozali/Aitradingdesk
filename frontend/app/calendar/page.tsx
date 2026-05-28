import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import CalendarControls from "./CalendarControls";
import { safeFetch } from "@/lib/api";
import type { EconomicEvent, SchedulerStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function CalendarPage() {
  const [events, status] = await Promise.all([
    safeFetch<EconomicEvent[]>(
      "/calendar/upcoming?hours=168&relevant_only=true",
    ),
    safeFetch<SchedulerStatus>("/calendar/scheduler/status"),
  ]);

  return (
    <>
      <PageHeader
        title="Economic Calendar"
        description="High-impact catalysts (CPI, NFP, FOMC, PCE, Powell, rate decisions). Sync into the FR-13 news catalyst gate from here."
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
              <span className="font-mono">{status.data.provider ?? "—"}</span>
              <div className="text-shadow-muted">Sync symbol</div>
              <span className="font-mono">
                {status.data.symbols.join(", ") || "XAUUSD"}
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
              {status.data.last_error && (
                <>
                  <div className="text-shadow-muted">Last error</div>
                  <span className="text-xs text-shadow-err">
                    {status.data.last_error}
                  </span>
                </>
              )}
            </div>
          ) : null}
        </Panel>

        <Panel heading="Controls">
          <CalendarControls />
        </Panel>
      </div>

      <Panel heading="Upcoming Relevant Events (7d)" className="mt-4">
        {events.error ? (
          <ErrorPanel message={events.error} />
        ) : events.data && events.data.length ? (
          <table className="w-full text-left text-xs">
            <thead className="text-shadow-muted">
              <tr>
                <th className="px-2 py-1">When (UTC)</th>
                <th className="px-2 py-1">Country</th>
                <th className="px-2 py-1">Event</th>
                <th className="px-2 py-1">Impact</th>
                <th className="px-2 py-1">Forecast</th>
                <th className="px-2 py-1">Previous</th>
                <th className="px-2 py-1">Actual</th>
                <th className="px-2 py-1">Provider</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {events.data.map((e) => (
                <tr key={e.id} className="border-t border-shadow-border">
                  <td className="px-2 py-1 whitespace-nowrap">
                    {new Date(e.scheduled_at_utc).toLocaleString()}
                  </td>
                  <td className="px-2 py-1">{e.country}</td>
                  <td className="px-2 py-1 font-sans">{e.event_name}</td>
                  <td className="px-2 py-1">
                    <StatusPill value={e.impact} />
                  </td>
                  <td className="px-2 py-1">{e.forecast ?? "—"}</td>
                  <td className="px-2 py-1">{e.previous ?? "—"}</td>
                  <td className="px-2 py-1">{e.actual ?? "—"}</td>
                  <td className="px-2 py-1 text-shadow-muted">{e.provider}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState
            title="No upcoming events"
            description="POST /calendar/refresh to pull the next week from the configured provider."
          />
        )}
      </Panel>
    </>
  );
}
