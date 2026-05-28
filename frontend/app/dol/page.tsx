import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import SymbolPicker from "@/components/SymbolPicker";
import { DEFAULT_SYMBOL, safeFetch } from "@/lib/api";
import { idText } from "@/lib/i18n";
import type { DolObjective, DolResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DolPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string }>;
}) {
  const params = await searchParams;
  const symbol = (params.symbol || DEFAULT_SYMBOL).toUpperCase();
  const dol = await safeFetch<DolResponse>(`/dol/current/${symbol}`);

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
    </>
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
