"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { approxAltitudeKm } from "@/lib/orbital";
import { PageHeader, Panel, LoadingState, ErrorState, EmptyState } from "@/components/Panel";
import { StatReadout } from "@/components/StatReadout";
import { SeverityBadge, severityColor } from "@/components/SeverityBadge";
import type { Severity } from "@/types/api";

const CHART_GRID = "#1e2731";
const CHART_TEXT = "#7c8a99";

export default function OverviewPage() {
  const objects = useApiData(() => api.listObjects({ page_size: 500 }));
  const conjunctions = useApiData(() => api.listConjunctions({ page_size: 200 }));

  const objectTypeCounts = useMemo(() => {
    if (!objects.data) return null;
    const counts = { ACTIVE_SATELLITE: 0, DEBRIS: 0, ROCKET_BODY: 0, UNKNOWN: 0 };
    for (const o of objects.data) counts[o.object_type]++;
    return counts;
  }, [objects.data]);

  const severityCounts = useMemo(() => {
    if (!conjunctions.data) return null;
    const counts: Record<Severity, number> = { LOW: 0, MODERATE: 0, HIGH: 0, CRITICAL: 0 };
    for (const c of conjunctions.data) counts[c.severity]++;
    return counts;
  }, [conjunctions.data]);

  const altitudeBands = useMemo(() => {
    if (!objects.data) return null;
    const bands = new Map<number, number>();
    for (const o of objects.data) {
      const alt = approxAltitudeKm(o);
      const band = Math.floor(alt / 200) * 200;
      bands.set(band, (bands.get(band) ?? 0) + 1);
    }
    return Array.from(bands.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([band, count]) => ({ band: `${band}-${band + 200}`, count }));
  }, [objects.data]);

  const objectTypeChartData = objectTypeCounts
    ? [
        { type: "Satellites", count: objectTypeCounts.ACTIVE_SATELLITE },
        { type: "Debris", count: objectTypeCounts.DEBRIS },
        { type: "Rocket bodies", count: objectTypeCounts.ROCKET_BODY },
        { type: "Unknown", count: objectTypeCounts.UNKNOWN },
      ]
    : [];

  const severityChartData = severityCounts
    ? (["LOW", "MODERATE", "HIGH", "CRITICAL"] as Severity[]).map((s) => ({
        severity: s,
        count: severityCounts[s],
      }))
    : [];

  const topEvents = (conjunctions.data ?? [])
    .slice()
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 6);

  const highRisk = severityCounts ? severityCounts.HIGH + severityCounts.CRITICAL : 0;

  return (
    <div>
      <PageHeader
        title="Overview"
        description="DETECT -> TRACK -> PREDICT -> ASSESS -> ALERT -> MITIGATE -> PRIORITIZE"
      />

      {objects.error && <ErrorState message={objects.error} />}
      {conjunctions.error && !objects.error && <ErrorState message={conjunctions.error} />}

      {!objects.error && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
            <StatReadout label="Tracked objects" value={objects.data?.length ?? "--"} />
            <StatReadout
              label="Active satellites"
              value={objectTypeCounts?.ACTIVE_SATELLITE ?? "--"}
            />
            <StatReadout label="Debris objects" value={objectTypeCounts?.DEBRIS ?? "--"} />
            <StatReadout label="Rocket bodies" value={objectTypeCounts?.ROCKET_BODY ?? "--"} />
            <StatReadout label="Conjunctions" value={conjunctions.data?.length ?? "--"} />
            <StatReadout label="High risk events" value={highRisk || "--"} accent="high" />
            <StatReadout
              label="Critical events"
              value={severityCounts?.CRITICAL ?? "--"}
              accent="critical"
            />
          </div>

          <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel title="Objects by type">
              {objects.loading ? (
                <LoadingState />
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={objectTypeChartData}>
                    <CartesianGrid stroke={CHART_GRID} vertical={false} />
                    <XAxis dataKey="type" stroke={CHART_TEXT} fontSize={12} />
                    <YAxis stroke={CHART_TEXT} fontSize={12} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        background: "#12181f",
                        border: "1px solid #1e2731",
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" fill="#4fd8c4" radius={0} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Panel>

            <Panel title="Risk distribution">
              {conjunctions.loading ? (
                <LoadingState />
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={severityChartData}>
                    <CartesianGrid stroke={CHART_GRID} vertical={false} />
                    <XAxis dataKey="severity" stroke={CHART_TEXT} fontSize={12} />
                    <YAxis stroke={CHART_TEXT} fontSize={12} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        background: "#12181f",
                        border: "1px solid #1e2731",
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" radius={0}>
                      {severityChartData.map((entry) => (
                        <Cell key={entry.severity} fill={severityColor(entry.severity)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Panel>
          </div>

          <div className="mb-6">
            <Panel title="Objects by altitude band (km)">
              {objects.loading ? (
                <LoadingState />
              ) : altitudeBands && altitudeBands.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={altitudeBands}>
                    <CartesianGrid stroke={CHART_GRID} vertical={false} />
                    <XAxis dataKey="band" stroke={CHART_TEXT} fontSize={11} />
                    <YAxis stroke={CHART_TEXT} fontSize={12} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        background: "#12181f",
                        border: "1px solid #1e2731",
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" fill="#4fd8c4" radius={0} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState message="No object data yet." />
              )}
            </Panel>
          </div>

          <Panel
            title="Top-risk conjunctions"
            action={
              <Link href="/conjunctions" className="text-xs text-accent hover:underline">
                View all
              </Link>
            }
          >
            {conjunctions.loading ? (
              <LoadingState />
            ) : topEvents.length === 0 ? (
              <EmptyState message="No conjunctions screened yet. Run a screening pass from the Conjunctions page." />
            ) : (
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-text-muted">
                    <th className="pb-2 font-normal">Event</th>
                    <th className="pb-2 font-normal">Objects</th>
                    <th className="pb-2 font-normal">Miss distance</th>
                    <th className="pb-2 font-normal">Risk score</th>
                    <th className="pb-2 font-normal">Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {topEvents.map((e) => (
                    <tr key={e.event_id} className="border-b border-border/60 last:border-0">
                      <td className="py-2">
                        <Link
                          href={`/conjunctions/${e.event_id}`}
                          className="tabular text-accent hover:underline"
                        >
                          {e.event_id}
                        </Link>
                      </td>
                      <td className="py-2 text-text-muted">
                        {e.primary_object_name} / {e.secondary_object_name}
                      </td>
                      <td className="py-2 tabular">{e.miss_distance_km.toFixed(3)} km</td>
                      <td className="py-2 tabular">{e.risk_score.toFixed(2)}</td>
                      <td className="py-2">
                        <SeverityBadge severity={e.severity} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
