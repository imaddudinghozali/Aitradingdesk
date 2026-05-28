import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import SymbolPicker from "@/components/SymbolPicker";
import { DEFAULT_SYMBOL, safeFetch } from "@/lib/api";
import { idText } from "@/lib/i18n";
import type {
  DolObjective,
  DolResponse,
  MultiTfDolResponse,
  TimeframeContext,
} from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DolPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string }>;
}) {
  const params = await searchParams;
  const symbol = (params.symbol || DEFAULT_SYMBOL).toUpperCase();
  const [dol, multitf] = await Promise.all([
    safeFetch<DolResponse>(`/dol/current/${symbol}`),
    safeFetch<MultiTfDolResponse>(`/dol/multitf/${symbol}`),
  ]);

  return (
    <>
      <PageHeader
        title="DOL Status"
        description="Assessment Draw on Liquidity dengan lifecycle gate. Shift DOL wajib punya objective lama resolved, displacement, timing, dan narrative sebelumnya resolved."
        actions={<SymbolPicker defaultSymbol={DEFAULT_SYMBOL} />}
      />
      {dol.error && dol.error.startsWith("404") ? (
        <EmptyState
          title={`Belum ada assessment DOL untuk ${symbol}`}
          description="POST /dol/evaluate via backend untuk menghitung DOL pertama."
        />
      ) : dol.error ? (
        <ErrorPanel message={dol.error} />
      ) : dol.data ? (
        <DolDetail dol={dol.data} />
      ) : null}

      <Panel heading="Konteks DOL Multi-Timeframe (Parent → Child)" className="mt-4">
        {multitf.error ? (
          <ErrorPanel message={multitf.error} />
        ) : multitf.data ? (
          <MultiTfView data={multitf.data} />
        ) : (
          <EmptyState title="Konteks multi-timeframe belum tersedia" />
        )}
      </Panel>
    </>
  );
}

const DRAW_STYLE: Record<string, string> = {
  up: "text-shadow-ok",
  down: "text-shadow-err",
  neutral: "text-shadow-muted",
};
const STATUS_STYLE: Record<string, string> = {
  root: "text-shadow-accent",
  aligned: "text-shadow-ok",
  corrective: "text-shadow-warn",
  neutral: "text-shadow-muted",
  no_data: "text-shadow-muted",
};
const CONFLICT_STYLE: Record<string, string> = {
  none: "text-shadow-ok",
  minor: "text-shadow-warn",
  major: "text-shadow-err",
};

function drawArrow(draw: string): string {
  return draw === "up" ? "▲ up" : draw === "down" ? "▼ down" : "• neutral";
}

function MultiTfView({ data }: { data: MultiTfDolResponse }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
        <span>
          <span className="text-shadow-muted">Konflik: </span>
          <span className={CONFLICT_STYLE[data.conflict_level] ?? ""}>
            {data.conflict_level.toUpperCase()}
          </span>
        </span>
        <span className="text-xs text-shadow-muted">{idText(data.active_dol)}</span>
      </div>
      <div
        className={`rounded border border-shadow-border bg-shadow-bg/30 p-2 text-xs ${
          CONFLICT_STYLE[data.conflict_level] ?? ""
        }`}
      >
        {idText(data.execution_hint)}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-shadow-muted">
            <tr>
              <th className="py-1 pr-3">Timeframe</th>
              <th className="py-1 pr-3">Draw</th>
              <th className="py-1 pr-3">Model</th>
              <th className="py-1 pr-3">Posisi</th>
              <th className="py-1 pr-3">vs Parent</th>
              <th className="py-1">Catatan</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {data.contexts.map((c) => (
              <Row key={c.timeframe} c={c} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Row({ c }: { c: TimeframeContext }) {
  return (
    <tr className="border-t border-shadow-border/50">
      <td className="py-1 pr-3 text-shadow-ink">{c.timeframe}</td>
      <td className={`py-1 pr-3 ${c.frame ? DRAW_STYLE[c.frame.draw] ?? "" : ""}`}>
        {c.frame ? drawArrow(c.frame.draw) : "-"}
      </td>
      <td className="py-1 pr-3">{c.frame?.model ?? "-"}</td>
      <td className="py-1 pr-3">{c.frame ? idText(c.frame.position) : "-"}</td>
      <td className={`py-1 pr-3 ${STATUS_STYLE[c.parent_status] ?? ""}`}>
        {idText(c.parent_status)}
      </td>
      <td className="py-1 font-sans text-shadow-muted">{idText(c.note)}</td>
    </tr>
  );
}

function DolDetail({ dol }: { dol: DolResponse }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel
        heading="Assessment DOL"
        actions={<StatusPill value={dol.lifecycle_status} />}
      >
        <div className="kv">
          <div className="text-shadow-muted">Symbol</div>
          <span>{dol.symbol}</span>
          <div className="text-shadow-muted">Arah Delivery</div>
          <span>{idText(dol.delivery_direction ?? "n/a")}</span>
          <div className="text-shadow-muted">Kualitas Objective</div>
          <span>{idText(dol.objective_quality ?? "waiting")}</span>
          <div className="text-shadow-muted">Eksekusi</div>
          <span>{idText(dol.execution_status)}</span>
          <div className="text-shadow-muted">Per</div>
          <span className="font-mono text-xs">
            {new Date(dol.as_of_utc).toLocaleString()}
          </span>
          <div className="text-shadow-muted">Alasan</div>
          <span className="text-xs">{idText(dol.status_reason)}</span>
        </div>
      </Panel>

      <Panel heading="Objective Likuiditas DOL">
        {dol.primary_dol || dol.engineered_liquidity ? (
          <div className="kv">
            <div className="text-shadow-muted">DOL Utama</div>
            <span>{formatObjective(dol.primary_dol)}</span>
            <div className="text-shadow-muted">DOL Sekunder</div>
            <span>{formatObjective(dol.secondary_dol)}</span>
            <div className="text-shadow-muted">Objective HTF</div>
            <span>{formatObjective(dol.htf_objective)}</span>
            <div className="text-shadow-muted">Objective Intraday</div>
            <span>{formatObjective(dol.intraday_objective)}</span>
            <div className="text-shadow-muted">Engineered</div>
            <span>{formatObjective(dol.engineered_liquidity)}</span>
          </div>
        ) : (
          <EmptyState title="Belum ada objective referensi yang resolved" />
        )}
      </Panel>
    </div>
  );
}

function formatObjective(objective: DolObjective | null): string {
  if (!objective) return "n/a";
  return `${objective.level_type} ${objective.liquidity_side} @ ${objective.price} (${idText(objective.liquidity_status)})`;
}
