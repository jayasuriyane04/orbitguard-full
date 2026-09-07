"use client";

import { useState } from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";

import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { PageHeader, Panel, LoadingState, ErrorState, EmptyState } from "@/components/Panel";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { Severity } from "@/types/api";

const SEVERITIES: { value: Severity | ""; label: string }[] = [
  { value: "", label: "All severities" },
  { value: "CRITICAL", label: "Critical" },
  { value: "HIGH", label: "High" },
  { value: "MODERATE", label: "Moderate" },
  { value: "LOW", label: "Low" },
];

export default function ConjunctionsPage() {
  const [severity, setSeverity] = useState<Severity | "">("");
  const [screening, setScreening] = useState(false);
  const [screeningError, setScreeningError] = useState<string | null>(null);

  const conjunctions = useApiData(
    () => api.listConjunctions({ severity: severity || undefined, page_size: 100 }),
    [severity]
  );

  async function runScreening() {
    setScreening(true);
    setScreeningError(null);
    try {
      await api.screenConjunctions({
        window_hours: 24,
        step_seconds: 30,
        miss_distance_threshold_km: 25,
        persist: true,
      });
      conjunctions.reload();
    } catch (err) {
      setScreeningError(err instanceof Error ? err.message : String(err));
    } finally {
      setScreening(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Conjunctions"
        description="Two-stage screening results: predicted close approaches, ranked by risk score."
        action={
          <button
            onClick={runScreening}
            disabled={screening}
            className="flex items-center gap-2 border border-accent px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-50"
          >
            <RefreshCw size={14} className={screening ? "animate-spin" : ""} />
            {screening ? "Screening..." : "Run screening pass"}
          </button>
        }
      />

      {screeningError && (
        <div className="mb-4">
          <ErrorState message={screeningError} />
        </div>
      )}

      <div className="mb-4">
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value as Severity | "")}
          className="border border-border bg-panel px-3 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
        >
          {SEVERITIES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <Panel>
        {conjunctions.loading ? (
          <LoadingState />
        ) : conjunctions.error ? (
          <ErrorState message={conjunctions.error} />
        ) : !conjunctions.data || conjunctions.data.length === 0 ? (
          <EmptyState message='No conjunctions on file yet. Click "Run screening pass" to detect close approaches.' />
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-text-muted">
                <th className="pb-2 font-normal">Event</th>
                <th className="pb-2 font-normal">Objects</th>
                <th className="pb-2 font-normal">TCA</th>
                <th className="pb-2 font-normal">Miss distance</th>
                <th className="pb-2 font-normal">Rel. velocity</th>
                <th className="pb-2 font-normal">Risk score</th>
                <th className="pb-2 font-normal">Severity</th>
              </tr>
            </thead>
            <tbody>
              {conjunctions.data.map((c) => (
                <tr key={c.event_id} className="border-b border-border/60 last:border-0">
                  <td className="py-2">
                    <Link
                      href={`/conjunctions/${c.event_id}`}
                      className="tabular text-accent hover:underline"
                    >
                      {c.event_id}
                    </Link>
                  </td>
                  <td className="py-2 text-text-muted">
                    {c.primary_object_name} / {c.secondary_object_name}
                  </td>
                  <td className="py-2 tabular">{new Date(c.tca).toLocaleString()}</td>
                  <td className="py-2 tabular">{c.miss_distance_km.toFixed(3)} km</td>
                  <td className="py-2 tabular">{c.relative_velocity_km_s.toFixed(3)} km/s</td>
                  <td className="py-2 tabular">{c.risk_score.toFixed(2)}</td>
                  <td className="py-2">
                    <SeverityBadge severity={c.severity} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
