import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import SymbolPicker from "@/components/SymbolPicker";
import { DEFAULT_SYMBOL, safeFetch } from "@/lib/api";
import { idText } from "@/lib/i18n";
import type {
  AlertRecord,
  NarrativeSnapshot,
  QuarterReadinessResponse,
} from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ActiveNarrativeBoardPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string }>;
}) {
  const params = await searchParams;
  const symbol = (params.symbol || DEFAULT_SYMBOL).toUpperCase();

  const [narrative, quarter, alerts] = await Promise.all([
    safeFetch<NarrativeSnapshot>(`/narratives/latest/${symbol}`),
    safeFetch<QuarterReadinessResponse>(
      `/quarter-readiness/current/${symbol}`,
    ),
    safeFetch<AlertRecord[]>("/alerts?limit=5"),
  ]);

  return (
    <>
      <PageHeader
        title="Board Narrative Aktif"
        description="Snapshot Market Delivery terbaru, kesiapan quarter Daye, dan alert terakhir. Baca top-down: DOL dulu, eksekusi terakhir."
        actions={<SymbolPicker defaultSymbol={DEFAULT_SYMBOL} />}
      />

      {narrative.error && narrative.error.startsWith("404") ? (
        <EmptyState
          title={`Belum ada snapshot narrative untuk ${symbol}`}
          description="POST /narratives/generate via backend untuk membuat Snapshot Market Delivery pertama."
        />
      ) : narrative.error ? (
        <ErrorPanel
          message={narrative.error}
          hint="Pastikan backend berjalan dan DATABASE_URL sudah dikonfigurasi."
        />
      ) : (
        narrative.data && <NarrativeBoard snapshot={narrative.data} />
      )}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <Panel heading="Kesiapan Quarter">
          {quarter.error && quarter.error.startsWith("404") ? (
            <EmptyState
              title={`Belum ada kesiapan quarter untuk ${symbol}`}
              description="Jalankan evaluasi DOL dan quarter readiness setelah data market tersedia."
            />
          ) : quarter.error ? (
            <ErrorPanel message={quarter.error} />
          ) : quarter.data ? (
            <div className="kv">
              <div className="text-shadow-muted">Daye Quarter</div>
              <StatusPill value={quarter.data.daily_quarter} />
              <div className="text-shadow-muted">Status</div>
              <StatusPill value={quarter.data.quarter_status} />
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
              <div className="text-shadow-muted">Keputusan Gate</div>
              <span>{idText(quarter.data.gate_decision)}</span>
            </div>
          ) : (
            <EmptyState title="Belum ada kesiapan quarter" />
          )}
        </Panel>

        <Panel heading="Alert Terbaru">
          {alerts.error ? (
            <div className="text-xs text-shadow-muted">{idText(alerts.error)}</div>
          ) : alerts.data && alerts.data.length ? (
            <ul className="space-y-2 text-xs">
              {alerts.data.map((alert) => (
                <li
                  key={alert.id}
                  className="border-l-2 border-shadow-border pl-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-shadow-muted">
                      {new Date(alert.created_at).toLocaleString()}
                    </span>
                    <StatusPill value={alert.severity} />
                  </div>
                  <div className="mt-0.5 line-clamp-2 text-shadow-ink">
                    {idText(alert.message)}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="Belum ada alert" />
          )}
        </Panel>
      </div>
    </>
  );
}

function NarrativeBoard({ snapshot }: { snapshot: NarrativeSnapshot }) {
  const rows: [string, string][] = [
    ["Sesi", snapshot.session],
    ["Anchor Sesi", snapshot.session_anchor],
    ["Quarter (QT)", snapshot.daily_quarter],
    ["HTF DOL", snapshot.htf_dol],
    ["Arah Likuiditas", snapshot.direction_liquidity],
    ["Model Aktif", snapshot.active_model],
    ["State Delivery", snapshot.delivery_state],
    ["Narrative Sesi", snapshot.session_narrative],
    ["Judas / Manipulasi", snapshot.judas_manipulation_status],
    ["SSMT XAU-XAG", snapshot.ssmt_status],
    ["Kualitas Ekspansi", snapshot.expansion_quality],
    ["Invalidation", snapshot.invalidation],
    ["Target Likuiditas (HTF DOL)", snapshot.target_liquidity],
    ["Referensi Retracement", snapshot.retracement_reference || "Tidak ada yang dekat"],
  ];

  return (
    <Panel
      heading="SNAPSHOT MARKET DELIVERY"
      actions={<StatusPill value={snapshot.execution_status} />}
    >
      <div className="mb-3 text-xs text-shadow-muted">
        {snapshot.symbol} - per{" "}
        <span className="font-mono">
          {new Date(snapshot.as_of_utc).toLocaleString()}
        </span>
      </div>
      <div className="kv">
        {rows.map(([label, value]) => (
          <FragmentRow key={label} label={label} value={value} />
        ))}
      </div>
    </Panel>
  );
}

function FragmentRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <div className="text-shadow-muted">{label}</div>
      <div className="text-shadow-ink">{idText(value)}</div>
    </>
  );
}
