import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import { safeFetch } from "@/lib/api";
import { idText } from "@/lib/i18n";
import type { SsmtResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SsmtPage() {
  const ssmt = await safeFetch<SsmtResponse>("/ssmt/current");
  return (
    <>
      <PageHeader
        title="SSMT XAU / XAG"
        description="Engine SSMT 5-filter: CIC, liquidity swept, POI touched, quarter Daye berurutan, konteks algoritma, alignment DOL, dan Magneto tidak trigger."
      />
      {ssmt.error && ssmt.error.startsWith("404") ? (
        <EmptyState
          title="Belum ada event SSMT"
          description="POST /ssmt/evaluate dengan poi_touched=true setelah HTF POI direview."
        />
      ) : ssmt.error ? (
        <ErrorPanel message={ssmt.error} />
      ) : ssmt.data ? (
        <Panel
          heading="SSMT Terbaru"
          actions={<StatusPill value={ssmt.data.ssmt_status} />}
        >
          <div className="kv">
            <div className="text-shadow-muted">Asset Trade</div>
            <span>{ssmt.data.trade_asset}</span>
            <div className="text-shadow-muted">Pair Konfirmasi</div>
            <span>{ssmt.data.confirmation_symbol}</span>
            <div className="text-shadow-muted">State Relatif XAU</div>
            <StatusPill value={ssmt.data.xau_relative_state} />
            <div className="text-shadow-muted">CIC</div>
            <span>{ssmt.data.cic_detected ? "terdeteksi" : "belum terdeteksi"}</span>
            <div className="text-shadow-muted">Arah</div>
            <span>{idText(ssmt.data.direction ?? "waiting")}</span>
            <div className="text-shadow-muted">Sequence Quarter Valid</div>
            <span>{ssmt.data.quarter_sequence_valid ? "ya" : "tidak"}</span>
            <div className="text-shadow-muted">Quarters</div>
            <span>
              {ssmt.data.first_quarter ?? "n/a"} - {ssmt.data.second_quarter ?? "n/a"}
            </span>
            <div className="text-shadow-muted">POI Touched</div>
            <span>{ssmt.data.poi_touched ? "ya" : "tidak"}</span>
            <div className="text-shadow-muted">Konteks Algoritma</div>
            <span>{idText(ssmt.data.algorithm_context_status)}</span>
            <div className="text-shadow-muted">Alignment DOL</div>
            <span>{idText(ssmt.data.ssmt_dol_alignment)}</span>
            <div className="text-shadow-muted">Magneto</div>
            <span>{idText(ssmt.data.magneto_status)}</span>
            <div className="text-shadow-muted">Konteks Likuiditas</div>
            <span className="text-xs">{idText(ssmt.data.liquidity_context)}</span>
            <div className="text-shadow-muted">Alasan</div>
            <span className="text-xs">{idText(ssmt.data.status_reason)}</span>
          </div>
        </Panel>
      ) : null}
    </>
  );
}
