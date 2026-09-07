"use client";

import { useState } from "react";
import { Check } from "lucide-react";

import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { PageHeader, Panel, LoadingState, ErrorState, EmptyState } from "@/components/Panel";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { AlertStatus } from "@/types/api";

const STATUSES: { value: AlertStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "NEW", label: "New" },
  { value: "ACKNOWLEDGED", label: "Acknowledged" },
  { value: "RESOLVED", label: "Resolved" },
];

export default function AlertsPage() {
  const [status, setStatus] = useState<AlertStatus | "">("");
  const [ackingId, setAckingId] = useState<number | null>(null);
  const alerts = useApiData(() => api.listAlerts({ status: status || undefined, page_size: 100 }), [status]);

  async function acknowledge(id: number) {
    setAckingId(id);
    try {
      await api.acknowledgeAlert(id);
      alerts.reload();
    } finally {
      setAckingId(null);
    }
  }

  return (
    <div>
      <PageHeader
        title="Alerts"
        description="Auto-generated for HIGH/CRITICAL conjunctions or sub-threshold miss distance."
      />

      <div className="mb-4">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as AlertStatus | "")}
          className="border border-border bg-panel px-3 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <Panel>
        {alerts.loading ? (
          <LoadingState />
        ) : alerts.error ? (
          <ErrorState message={alerts.error} />
        ) : !alerts.data || alerts.data.length === 0 ? (
          <EmptyState message="No alerts on file." />
        ) : (
          <ul className="divide-y divide-border/60">
            {alerts.data.map((a) => (
              <li key={a.id} className="flex items-start justify-between gap-4 py-3">
                <div>
                  <div className="mb-1 flex items-center gap-2">
                    <SeverityBadge severity={a.severity} />
                    <span className="text-sm font-medium">{a.title}</span>
                  </div>
                  <p className="text-xs text-text-muted">{a.message}</p>
                  <p className="mt-1 text-xs text-text-muted tabular">
                    {new Date(a.created_at).toLocaleString()} -- {a.status}
                  </p>
                </div>
                {a.status === "NEW" && (
                  <button
                    onClick={() => acknowledge(a.id)}
                    disabled={ackingId === a.id}
                    className="flex shrink-0 items-center gap-1.5 border border-border px-3 py-1.5 text-xs text-text-muted hover:border-accent hover:text-accent disabled:opacity-50"
                  >
                    <Check size={13} />
                    Acknowledge
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
