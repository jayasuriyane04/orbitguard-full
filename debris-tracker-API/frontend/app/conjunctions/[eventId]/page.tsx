"use client";

import { use, useState } from "react";
import { Rocket } from "lucide-react";

import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { PageHeader, Panel, LoadingState, ErrorState, EmptyState } from "@/components/Panel";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { ManeuverCandidate } from "@/types/api";

export default function ConjunctionDetailPage({
  params,
}: {
  params: Promise<{ eventId: string }>;
}) {
  const { eventId } = use(params);
  const event = useApiData(() => api.getConjunction(eventId), [eventId]);

  const [maneuvers, setManeuvers] = useState<ManeuverCandidate[] | null>(null);
  const [maneuverLoading, setManeuverLoading] = useState(false);
  const [maneuverError, setManeuverError] = useState<string | null>(null);

  async function generateManeuver() {
    setManeuverLoading(true);
    setManeuverError(null);
    setManeuvers(null);
    try {
      const result = await api.generateManeuver(eventId);
      setManeuvers(result);
    } catch (err) {
      setManeuverError(err instanceof Error ? err.message : String(err));
    } finally {
      setManeuverLoading(false);
    }
  }

  if (event.loading) return <LoadingState />;
  if (event.error) return <ErrorState message={event.error} />;
  if (!event.data) return null;

  const e = event.data;
  const best = maneuvers?.[0];

  return (
    <div>
      <PageHeader
        title={e.event_id}
        description={`${e.primary_object_name} (NORAD ${e.primary_object}) vs. ${e.secondary_object_name} (NORAD ${e.secondary_object})`}
      />

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Conjunction summary">
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-text-muted">Time of closest approach</dt>
            <dd className="tabular">{new Date(e.tca).toLocaleString()}</dd>
            <dt className="text-text-muted">Miss distance</dt>
            <dd className="tabular">{e.miss_distance_km.toFixed(4)} km</dd>
            <dt className="text-text-muted">Relative velocity</dt>
            <dd className="tabular">{e.relative_velocity_km_s.toFixed(4)} km/s</dd>
            <dt className="text-text-muted">Risk score</dt>
            <dd className="tabular">{e.risk_score.toFixed(3)}</dd>
            <dt className="text-text-muted">Severity</dt>
            <dd>
              <SeverityBadge severity={e.severity} />
            </dd>
          </dl>
        </Panel>

        {e.factors && (
          <Panel title="Risk factor breakdown">
            <div className="space-y-3">
              {Object.entries(e.factors).map(([factor, value]) => (
                <div key={factor}>
                  <div className="mb-1 flex justify-between text-xs text-text-muted">
                    <span className="capitalize">{factor.replace("_", " ")}</span>
                    <span className="tabular">{value.toFixed(2)}</span>
                  </div>
                  <div className="h-1.5 w-full bg-border">
                    <div
                      className="h-1.5 bg-accent"
                      style={{ width: `${Math.round(value * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        )}
      </div>

      <Panel
        title="Avoidance maneuver simulator"
        action={
          <button
            onClick={generateManeuver}
            disabled={maneuverLoading}
            className="flex items-center gap-2 border border-accent px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-50"
          >
            <Rocket size={14} />
            {maneuverLoading ? "Simulating..." : "Generate avoidance maneuver"}
          </button>
        }
      >
        {maneuverError && <ErrorState message={maneuverError} />}

        {!maneuvers && !maneuverError && !maneuverLoading && (
          <EmptyState message="No maneuver generated yet for this event." />
        )}

        {best && (
          <div className="mb-4 border border-accent/40 bg-accent/5 p-4">
            <div className="mb-2 text-xs text-text-muted">
              Recommended candidate -- decision-support simulation, not an operational
              flight command
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-4">
              <div>
                <div className="text-xs text-text-muted">Direction</div>
                <div className="tabular">{best.direction}</div>
              </div>
              <div>
                <div className="text-xs text-text-muted">Delta-v</div>
                <div className="tabular">{best.delta_v_m_s.toFixed(3)} m/s</div>
              </div>
              <div>
                <div className="text-xs text-text-muted">Execute before TCA</div>
                <div className="tabular">{best.execute_before_tca_minutes} min</div>
              </div>
              <div>
                <div className="text-xs text-text-muted">Miss distance</div>
                <div className="tabular">
                  {best.original_miss_distance_km.toFixed(2)} to{" "}
                  {best.predicted_miss_distance_km.toFixed(2)} km
                </div>
              </div>
            </div>
          </div>
        )}

        {maneuvers && maneuvers.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-text-muted">
                <th className="pb-2 font-normal">Direction</th>
                <th className="pb-2 font-normal">Delta-v</th>
                <th className="pb-2 font-normal">Lead time</th>
                <th className="pb-2 font-normal">New miss distance</th>
                <th className="pb-2 font-normal">New risk score</th>
              </tr>
            </thead>
            <tbody>
              {maneuvers.map((m, i) => (
                <tr key={i} className="border-b border-border/60 last:border-0">
                  <td className="py-2">{m.direction}</td>
                  <td className="py-2 tabular">{m.delta_v_m_s.toFixed(3)} m/s</td>
                  <td className="py-2 tabular">{m.execute_before_tca_minutes} min</td>
                  <td className="py-2 tabular">{m.predicted_miss_distance_km.toFixed(3)} km</td>
                  <td className="py-2 tabular">{m.predicted_risk_score.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
