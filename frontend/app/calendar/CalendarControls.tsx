"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export default function CalendarControls() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function call(path: string, body: unknown = {}) {
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<unknown>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setMessage(
        typeof res === "object" ? JSON.stringify(res, null, 2) : String(res),
      );
      startTransition(() => router.refresh());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-3 text-xs">
      <div className="flex flex-wrap gap-2">
        <button
          className="rounded border border-shadow-border bg-shadow-bg px-3 py-1.5 hover:border-shadow-accent disabled:opacity-50"
          disabled={pending}
          onClick={() => call("/calendar/refresh", {})}
        >
          Refresh calendar
        </button>
        <button
          className="rounded border border-shadow-border bg-shadow-bg px-3 py-1.5 hover:border-shadow-accent disabled:opacity-50"
          disabled={pending}
          onClick={() =>
            call("/calendar/sync-to-catalyst", {
              symbol: "XAUUSD",
              lookahead_hours: 48,
            })
          }
        >
          Sync to catalyst gate
        </button>
        <button
          className="rounded border border-shadow-border bg-shadow-bg px-3 py-1.5 hover:border-shadow-accent disabled:opacity-50"
          disabled={pending}
          onClick={() => call("/calendar/scheduler/start", {})}
        >
          Start scheduler
        </button>
        <button
          className="rounded border border-shadow-border bg-shadow-bg px-3 py-1.5 hover:border-shadow-accent disabled:opacity-50"
          disabled={pending}
          onClick={() => call("/calendar/scheduler/stop", {})}
        >
          Stop scheduler
        </button>
      </div>
      {error && (
        <div className="rounded border border-shadow-err/40 bg-shadow-err/10 p-2 font-mono text-shadow-err">
          {error}
        </div>
      )}
      {message && (
        <pre className="max-h-40 overflow-auto rounded border border-shadow-border bg-shadow-bg/40 p-2 font-mono text-[10px] text-shadow-muted">
          {message}
        </pre>
      )}
      <p className="text-shadow-muted">
        Sync uses any active DOL; if missing it reports{" "}
        <span className="font-mono text-shadow-ink">skipped_missing_dol</span>{" "}
        and stays No Trade.
      </p>
    </div>
  );
}
