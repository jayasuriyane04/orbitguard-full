"use client";

import { Fragment, useState } from "react";

import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { PageHeader, Panel, LoadingState, ErrorState, EmptyState } from "@/components/Panel";
import type { RemovalPriority } from "@/types/api";

export default function DebrisPriorityPage() {
  const priorities = useApiData(() => api.getRemovalPriorities());
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <div>
      <PageHeader
        title="Debris removal priority"
        description="Ranked, non-maneuverable objects -- decision support for active-debris-removal mission planning. This never claims the platform can physically remove anything."
      />

      <Panel>
        {priorities.loading ? (
          <LoadingState />
        ) : priorities.error ? (
          <ErrorState message={priorities.error} />
        ) : !priorities.data || priorities.data.length === 0 ? (
          <EmptyState message="No removal-priority data yet. Run a conjunction screening pass first so priorities have events to rank against." />
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-text-muted">
                <th className="pb-2 font-normal">Rank</th>
                <th className="pb-2 font-normal">Object</th>
                <th className="pb-2 font-normal">NORAD ID</th>
                <th className="pb-2 font-normal">Conjunction count</th>
                <th className="pb-2 font-normal">Avg. severity</th>
                <th className="pb-2 font-normal">Priority score</th>
              </tr>
            </thead>
            <tbody>
              {priorities.data.map((p: RemovalPriority, i: number) => (
                <Fragment key={p.norad_id}>
                  <tr
                    className="cursor-pointer border-b border-border/60 hover:bg-white/[0.02]"
                    onClick={() => setExpanded(expanded === p.norad_id ? null : p.norad_id)}
                  >
                    <td className="py-2 tabular text-text-muted">{i + 1}</td>
                    <td className="py-2">{p.object_name}</td>
                    <td className="py-2 tabular">{p.norad_id}</td>
                    <td className="py-2 tabular">{p.conjunction_count}</td>
                    <td className="py-2 tabular">{p.average_severity_score.toFixed(2)}</td>
                    <td className="py-2 tabular">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 bg-border">
                          <div
                            className="h-1.5 bg-severity-high"
                            style={{ width: `${p.removal_priority_score}%` }}
                          />
                        </div>
                        {p.removal_priority_score.toFixed(1)}
                      </div>
                    </td>
                  </tr>
                  {expanded === p.norad_id && p.explanation && (
                    <tr className="border-b border-border/60">
                      <td />
                      <td colSpan={5} className="py-2 pr-4 text-xs text-text-muted">
                        {p.explanation}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
