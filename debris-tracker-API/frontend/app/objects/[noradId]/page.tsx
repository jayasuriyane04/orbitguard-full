"use client";

import { use } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { approxAltitudeKm } from "@/lib/orbital";
import { PageHeader, Panel, LoadingState, ErrorState } from "@/components/Panel";

export default function ObjectDetailPage({
  params,
}: {
  params: Promise<{ noradId: string }>;
}) {
  const { noradId } = use(params);
  const noradIdNum = Number(noradId);

  const object = useApiData(() => api.getObject(noradIdNum), [noradIdNum]);
  const trajectory = useApiData(
    () => api.getTrajectory(noradIdNum, 3, 120),
    [noradIdNum]
  );

  if (object.loading) return <LoadingState />;
  if (object.error) return <ErrorState message={object.error} />;
  if (!object.data) return null;

  const o = object.data;
  const altitudeSeries =
    trajectory.data?.points.map((p) => ({
      time: new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      altitude: p.altitude_km ?? 0,
    })) ?? [];

  return (
    <div>
      <PageHeader
        title={o.name}
        description={`NORAD ${o.norad_id} - ${o.object_type} - ${o.data_source}`}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Orbital elements">
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-text-muted">Inclination</dt>
            <dd className="tabular">{o.elements.inclination_deg.toFixed(4)} deg</dd>
            <dt className="text-text-muted">Eccentricity</dt>
            <dd className="tabular">{o.elements.eccentricity.toFixed(6)}</dd>
            <dt className="text-text-muted">RAAN</dt>
            <dd className="tabular">{o.elements.raan_deg.toFixed(4)} deg</dd>
            <dt className="text-text-muted">Argument of perigee</dt>
            <dd className="tabular">{o.elements.arg_perigee_deg.toFixed(4)} deg</dd>
            <dt className="text-text-muted">Mean anomaly</dt>
            <dd className="tabular">{o.elements.mean_anomaly_deg.toFixed(4)} deg</dd>
            <dt className="text-text-muted">Mean motion</dt>
            <dd className="tabular">{o.elements.mean_motion_rev_per_day.toFixed(6)} rev/day</dd>
            <dt className="text-text-muted">Approx. altitude</dt>
            <dd className="tabular">{approxAltitudeKm(o).toFixed(1)} km</dd>
            <dt className="text-text-muted">Maneuverable</dt>
            <dd>{o.maneuverable ? "Yes" : "No"}</dd>
            <dt className="text-text-muted">Epoch</dt>
            <dd className="tabular">{new Date(o.epoch).toISOString()}</dd>
          </dl>
        </Panel>

        <Panel title="Altitude over next 3 hours">
          {trajectory.loading ? (
            <LoadingState />
          ) : trajectory.error ? (
            <ErrorState message={trajectory.error} />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={altitudeSeries}>
                <CartesianGrid stroke="#1e2731" vertical={false} />
                <XAxis dataKey="time" stroke="#7c8a99" fontSize={11} />
                <YAxis stroke="#7c8a99" fontSize={11} domain={["auto", "auto"]} />
                <Tooltip
                  contentStyle={{ background: "#12181f", border: "1px solid #1e2731", fontSize: 12 }}
                />
                <Line
                  type="monotone"
                  dataKey="altitude"
                  stroke="#4fd8c4"
                  dot={false}
                  strokeWidth={1.5}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Panel>
      </div>

      {o.tle_line1 && o.tle_line2 && (
        <div className="mt-4">
          <Panel title="TLE">
            <pre className="tabular whitespace-pre-wrap text-xs text-text-muted">
              {o.tle_line1}
              {"\n"}
              {o.tle_line2}
            </pre>
          </Panel>
        </div>
      )}
    </div>
  );
}
