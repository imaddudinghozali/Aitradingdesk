import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ErrorPanel from "@/components/ErrorPanel";
import EmptyState from "@/components/EmptyState";
import { safeFetch } from "@/lib/api";
import { idText } from "@/lib/i18n";
import type { AlertRecord } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AlertsPage() {
  const alerts = await safeFetch<AlertRecord[]>("/alerts?limit=100");
  return (
    <>
      <PageHeader
        title="Riwayat Alert"
        description="Setiap snapshot narrative menyimpan alert. Delivery Telegram dicatat kembali pada row yang sama."
      />
      {alerts.error ? (
        <ErrorPanel message={alerts.error} />
      ) : alerts.data && alerts.data.length ? (
        <Panel>
          <table className="w-full text-left text-xs">
            <thead className="text-shadow-muted">
              <tr>
                <th className="px-2 py-1">Waktu</th>
                <th className="px-2 py-1">Tipe</th>
                <th className="px-2 py-1">Symbol</th>
                <th className="px-2 py-1">Severity</th>
                <th className="px-2 py-1">Telegram</th>
                <th className="px-2 py-1">Pesan</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {alerts.data.map((alert) => (
                <tr
                  key={alert.id}
                  className="border-t border-shadow-border align-top"
                >
                  <td className="px-2 py-1 whitespace-nowrap">
                    {new Date(alert.created_at).toLocaleString()}
                  </td>
                  <td className="px-2 py-1">{alert.event_type}</td>
                  <td className="px-2 py-1">{alert.symbol}</td>
                  <td className="px-2 py-1">
                    <StatusPill value={alert.severity} />
                  </td>
                  <td className="px-2 py-1">
                    {alert.sent_to_telegram ? "terkirim" : "antre"}
                  </td>
                  <td className="px-2 py-1 font-sans">{idText(alert.message)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      ) : (
        <EmptyState title="Belum ada alert" />
      )}
    </>
  );
}
