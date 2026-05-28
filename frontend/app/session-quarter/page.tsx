import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import SymbolPicker from "@/components/SymbolPicker";
import QuarterLadder from "@/components/QuarterLadder";
import { DEFAULT_SYMBOL, safeFetch } from "@/lib/api";
import { idText } from "@/lib/i18n";
import type {
  MarketSnapshot,
  QuarterLadderResponse,
  QuarterReadinessResponse,
} from "@/lib/types";

export const dynamic = "force-dynamic";

const QUARTER_GUIDE = [
  { q: "Q1", range: "18:00 - 00:00 NY", label: "Asia" },
  { q: "Q2", range: "00:00 - 06:00 NY", label: "London" },
  { q: "Q3", range: "06:00 - 12:00 NY", label: "NY AM" },
  { q: "Q4", range: "12:00 - 18:00 NY", label: "NY PM" },
];

export default async function SessionQuarterPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string }>;
}) {
  const params = await searchParams;
  const symbol = (params.symbol || DEFAULT_SYMBOL).toUpperCase();
  const [quarter, snapshots, ladder] = await Promise.all([
    safeFetch<QuarterReadinessResponse>(
      `/quarter-readiness/current/${symbol}`,
    ),
    safeFetch<MarketSnapshot[]>(
      `/market/snapshots?symbol=${symbol}&timeframe=M15&limit=1`,
    ),
    safeFetch<QuarterLadderResponse>(`/time/quarter-ladder`),
  ]);
  const latest = snapshots.data?.[0];

  return (
    <>
      <PageHeader
        title="Status Sesi & Quarter"
        description="Gate kesiapan Daye QT plus konteks snapshot terbaru yang tersimpan: sesi, anchor, dan micro-quarter."
        actions={<SymbolPicker defaultSymbol={DEFAULT_SYMBOL} />}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Panel
          heading="Gate Kesiapan Quarter"
          actions={
            quarter.data ? (
              <StatusPill value={quarter.data.quarter_status} />
            ) : null
          }
        >
          {quarter.error && quarter.error.startsWith("404") ? (
            <EmptyState title="Belum ada kesiapan quarter" />
          ) : quarter.error ? (
            <ErrorPanel message={quarter.error} />
          ) : quarter.data ? (
            <div className="kv">
              <div className="text-shadow-muted">Daye Quarter</div>
              <span>{quarter.data.daily_quarter}</span>
              <div className="text-shadow-muted">Sesi</div>
              <span>{idText(quarter.data.session)}</span>
              <div className="text-shadow-muted">Anchor</div>
              <span>{quarter.data.session_anchor}</span>
              <div className="text-shadow-muted">Alasan</div>
              <span className="text-xs">{idText(quarter.data.status_reason)}</span>
              {quarter.data.next_valid_window && (
                <>
                  <div className="text-shadow-muted">Window Berikutnya</div>
                  <span className="text-xs">
                    {idText(quarter.data.next_valid_window)}
                  </span>
                </>
              )}
            </div>
          ) : null}
        </Panel>

        <Panel heading="Konteks Waktu Snapshot Terbaru">
          {snapshots.error || !latest ? (
            <EmptyState
              title="Belum ada snapshot M15 tersimpan"
              description="POST /market/ohlc atau jalankan /market/ingest untuk mengisi data."
            />
          ) : (
            <div className="kv">
              <div className="text-shadow-muted">UTC</div>
              <span className="font-mono">
                {new Date(latest.timestamp_utc).toLocaleString()}
              </span>
              <div className="text-shadow-muted">NY</div>
              <span className="font-mono">
                {new Date(latest.timestamp_ny).toLocaleString()}
              </span>
              <div className="text-shadow-muted">Sesi</div>
              <span>{idText(latest.session)}</span>
              <div className="text-shadow-muted">Anchor</div>
              <span>{latest.session_anchor}</span>
              <div className="text-shadow-muted">Daily Quarter</div>
              <span>{latest.daily_quarter}</span>
              <div className="text-shadow-muted">Micro Quarter</div>
              <span>{latest.micro_quarter_90m}</span>
              <div className="text-shadow-muted">Hari</div>
              <span>{latest.day_of_week}</span>
              <div className="text-shadow-muted">Killzone</div>
              <span>{latest.is_killzone ? "ya" : "tidak"}</span>
            </div>
          )}
        </Panel>
      </div>

      <Panel heading="Tangga Waktu Daye (Fractal)" className="mt-4">
        {ladder.error ? (
          <ErrorPanel message={ladder.error} />
        ) : ladder.data ? (
          <div className="space-y-3 pt-2">
            <QuarterLadder ladder={ladder.data} />
            <div className="flex flex-wrap gap-3 text-[10px] text-shadow-muted">
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-3 rounded-sm bg-slate-500/60" />
                Q1 Akumulasi
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-3 rounded-sm bg-rose-500/60" />
                Q2 Manipulasi
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-3 rounded-sm bg-emerald-500/60" />
                Q3 Distribusi
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-3 rounded-sm bg-sky-500/60" />
                Q4 Kelanjutan
              </span>
            </div>
          </div>
        ) : (
          <EmptyState title="Tangga waktu tidak tersedia" />
        )}
      </Panel>

      <Panel heading="Referensi Daye QT" className="mt-4">
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
          {QUARTER_GUIDE.map((g) => (
            <div
              key={g.q}
              className="rounded border border-shadow-border bg-shadow-bg/30 p-3 text-xs"
            >
              <div className="font-mono text-shadow-accent">{g.q}</div>
              <div className="text-shadow-ink">{g.label}</div>
              <div className="text-shadow-muted">{g.range}</div>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
