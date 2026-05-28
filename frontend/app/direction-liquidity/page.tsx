import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import SymbolPicker from "@/components/SymbolPicker";
import { DEFAULT_SYMBOL, safeFetch } from "@/lib/api";
import type { IrlErlMappingResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DirectionLiquidityPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string }>;
}) {
  const params = await searchParams;
  const symbol = (params.symbol || DEFAULT_SYMBOL).toUpperCase();
  const mapping = await safeFetch<IrlErlMappingResponse>(
    `/direction-liquidity/current/${symbol}`,
  );

  return (
    <>
      <PageHeader
        title="IRL / ERL Direction Liquidity"
        description="Multi-timeframe direction liquidity flow with imbalance-aware mapping (FVG/OB on H1/H4)."
        actions={<SymbolPicker defaultSymbol={DEFAULT_SYMBOL} />}
      />

      {mapping.error && mapping.error.startsWith("404") ? (
        <EmptyState
          title={`No mapping for ${symbol}`}
          description="POST /direction-liquidity/evaluate to compute the first mapping."
        />
      ) : mapping.error ? (
        <ErrorPanel message={mapping.error} />
      ) : mapping.data ? (
        <MappingDetail mapping={mapping.data} />
      ) : null}
    </>
  );
}

function MappingDetail({ mapping }: { mapping: IrlErlMappingResponse }) {
  return (
    <div className="space-y-4">
      <Panel
        heading="Direction Flow"
        actions={
          <div className="flex gap-2">
            <StatusPill value={mapping.mapping_status} />
            <StatusPill value={mapping.direction_flow} tone="info" />
          </div>
        }
      >
        <div className="space-y-2 text-sm">
          <div className="text-shadow-ink">{mapping.status_reason}</div>
          <div className="text-xs text-shadow-muted">
            Execution: {mapping.execution_status}
          </div>
          {mapping.imbalance && (
            <div className="mt-3 rounded border border-shadow-info/30 bg-shadow-info/5 p-3 text-xs">
              <div className="font-medium text-shadow-info">
                Imbalance:{" "}
                <span className="font-mono">
                  {mapping.imbalance.timeframe} {mapping.imbalance.poi_type} (
                  {mapping.imbalance.direction})
                </span>{" "}
                — role: {mapping.imbalance_role}
              </div>
              <div className="mt-1 font-mono text-shadow-muted">
                {mapping.imbalance.price_low} — {mapping.imbalance.price_high}
              </div>
            </div>
          )}
          {mapping.conflict_flags.length > 0 && (
            <div className="mt-2 text-xs text-shadow-err">
              Conflicts: {mapping.conflict_flags.join("; ")}
            </div>
          )}
        </div>
      </Panel>

      <div className="grid gap-4 md:grid-cols-3">
        {mapping.layers.map((layer) => (
          <Panel
            key={layer.narrative_timeframe}
            heading={`${layer.narrative_timeframe} narrative`}
            actions={<StatusPill value={layer.status} />}
          >
            <div className="space-y-1 text-xs">
              <div className="text-shadow-muted">
                Direction TFs:{" "}
                <span className="font-mono text-shadow-ink">
                  {layer.direction_timeframes.join(", ")}
                </span>
              </div>
              <div className="text-shadow-muted">
                Direction Liquidity:{" "}
                <span className="text-shadow-ink">{layer.direction_liquidity}</span>
              </div>
              <div className="mt-2 text-shadow-ink">{layer.reason}</div>
              {layer.imbalance && (
                <div className="mt-2 text-shadow-info">
                  Layer imbalance: {layer.imbalance.timeframe}{" "}
                  {layer.imbalance.poi_type} ({layer.imbalance.direction})
                </div>
              )}
            </div>
          </Panel>
        ))}
      </div>

      {mapping.limitations.length > 0 && (
        <Panel heading="Declared Limitations">
          <ul className="list-disc space-y-1 pl-4 text-xs text-shadow-muted">
            {mapping.limitations.map((lim) => (
              <li key={lim}>{lim}</li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
