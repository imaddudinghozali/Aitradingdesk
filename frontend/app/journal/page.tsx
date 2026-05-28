import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import { safeFetch } from "@/lib/api";
import { idText } from "@/lib/i18n";
import type { JournalEntry } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function JournalPage() {
  const entries = await safeFetch<JournalEntry[]>("/journal");
  return (
    <>
      <PageHeader
        title="Journal"
        description="Konteks setup, alasan entry, konfirmasi, risiko, hasil, review kesalahan, dan review narrative per entry."
      />
      {entries.error ? (
        <ErrorPanel message={entries.error} />
      ) : entries.data && entries.data.length ? (
        <div className="space-y-3">
          {entries.data.map((entry) => (
            <Panel
              key={entry.id}
              heading={`#${entry.id} - ${entry.symbol}`}
              actions={
                entry.result ? <StatusPill value={entry.result} /> : null
              }
            >
              <div className="grid gap-3 text-xs md:grid-cols-2">
                <Block label="Konteks Setup" value={entry.setup_context} />
                <Block label="Alasan Entry" value={entry.entry_reason} />
                <Block label="Konfirmasi" value={entry.execution_confirmation} />
                <Block label="Risiko" value={entry.risk} />
                <Block label="Review Kesalahan" value={entry.mistake_review} />
                <Block label="Review Narrative" value={entry.narrative_review} />
              </div>
              <div className="mt-2 text-[10px] text-shadow-muted">
                {new Date(entry.created_at).toLocaleString()}
              </div>
            </Panel>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Belum ada entry journal"
          description="POST /journal untuk mencatat reasoning setelah setup."
        />
      )}
    </>
  );
}

function Block({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <div className="mb-0.5 text-[10px] uppercase tracking-wider text-shadow-muted">
        {label}
      </div>
      <div className="rounded border border-shadow-border bg-shadow-bg/40 p-2 text-shadow-ink">
        {idText(value)}
      </div>
    </div>
  );
}
