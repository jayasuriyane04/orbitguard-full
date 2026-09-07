"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { PageHeader, LoadingState, ErrorState } from "@/components/Panel";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { ObjectMarker } from "@/components/CesiumViewer";
import type { StateVector, TrackedObject, ConjunctionEvent } from "@/types/api";

const CesiumViewer = dynamic(() => import("@/components/CesiumViewer"), {
  ssr: false,
  loading: () => <LoadingState label="Loading 3D globe" />,
});

// Demo-scale cap: fetching one state-vector request per object. Fine for a
// hackathon-scale catalog (tens to low hundreds); a production deployment
// would add a batch state endpoint instead of N single requests.
const MAX_OBJECTS_ON_MAP = 150;

async function mapWithConcurrency<T, R>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<R | null>
): Promise<R[]> {
  const results: R[] = [];
  let index = 0;
  async function worker() {
    while (index < items.length) {
      const current = items[index++];
      const result = await fn(current).catch(() => null);
      if (result) results.push(result);
    }
  }
  await Promise.all(Array.from({ length: limit }, worker));
  return results;
}

export default function OrbitalMapPage() {
  const objects = useApiData(() => api.listObjects({ page_size: MAX_OBJECTS_ON_MAP }));
  const conjunctions = useApiData(() => api.listConjunctions({ severity: "CRITICAL", page_size: 10 }));

  const [markers, setMarkers] = useState<ObjectMarker[]>([]);
  const [statesLoading, setStatesLoading] = useState(true);
  const [showSatellites, setShowSatellites] = useState(true);
  const [showDebris, setShowDebris] = useState(true);
  const [showRocketBodies, setShowRocketBodies] = useState(true);
  const [showConjunctions, setShowConjunctions] = useState(false);
  const [showTrajectory, setShowTrajectory] = useState(true);

  const [selectedNoradId, setSelectedNoradId] = useState<number | null>(null);
  const [selectedObject, setSelectedObject] = useState<TrackedObject | null>(null);
  const [trajectoryPoints, setTrajectoryPoints] = useState<
    { x_km: number; y_km: number; z_km: number }[] | null
  >(null);

  const [conjunctionMarkers, setConjunctionMarkers] = useState<
    { event: ConjunctionEvent; state: StateVector }[]
  >([]);

  // fetch current state vectors for the loaded objects
  useEffect(() => {
    if (!objects.data) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- standard "set loading before fetch" pattern
    setStatesLoading(true);
    mapWithConcurrency(objects.data, 8, async (obj) => {
      const state = await api.getState(obj.norad_id);
      return { object: obj, state } as ObjectMarker;
    }).then((results) => {
      if (!cancelled) {
        setMarkers(results);
        setStatesLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [objects.data]);

  // fetch TCA state for top critical conjunctions when the toggle is on
  useEffect(() => {
    if (!showConjunctions || !conjunctions.data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clearing markers when the toggle turns off
      setConjunctionMarkers([]);
      return;
    }
    let cancelled = false;
    Promise.all(
      conjunctions.data.map(async (event) => {
        try {
          const state = await api.getState(event.primary_object, event.tca);
          return { event, state };
        } catch {
          return null;
        }
      })
    ).then((results) => {
      if (!cancelled) {
        setConjunctionMarkers(results.filter((r): r is { event: ConjunctionEvent; state: StateVector } => r !== null));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [showConjunctions, conjunctions.data]);

  const handleSelect = useCallback((noradId: number | null) => {
    setSelectedNoradId(noradId);
    setTrajectoryPoints(null);
    if (noradId == null) {
      setSelectedObject(null);
      return;
    }
    api.getObject(noradId).then(setSelectedObject).catch(() => setSelectedObject(null));
  }, []);

  useEffect(() => {
    if (!selectedNoradId || !showTrajectory) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clearing trajectory when selection/toggle clears
      setTrajectoryPoints(null);
      return;
    }
    api
      .getTrajectory(selectedNoradId, 1.5, 60)
      .then((traj) =>
        setTrajectoryPoints(traj.points.map((p) => ({ x_km: p.x_km, y_km: p.y_km, z_km: p.z_km })))
      )
      .catch(() => setTrajectoryPoints(null));
  }, [selectedNoradId, showTrajectory]);


  const visibleMarkers = useMemo(
    () =>
      markers.filter(({ object }) => {
        if (object.object_type === "ACTIVE_SATELLITE") return showSatellites;
        if (object.object_type === "DEBRIS") return showDebris;
        if (object.object_type === "ROCKET_BODY") return showRocketBodies;
        return true;
      }),
    [markers, showSatellites, showDebris, showRocketBodies]
  );

  const selectedConjunctionEvent = conjunctions.data?.find(
    (e) => e.primary_object === selectedNoradId
  );

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col">
      <PageHeader
        title="Orbital Map"
        description="Live-propagated positions. Click an object for details; toggle layers below."
      />

      <div className="mb-3 flex flex-wrap items-center gap-4 text-sm text-text-muted">
        <ToggleChip label="Satellites" checked={showSatellites} onChange={setShowSatellites} dotColor="#4fd8c4" />
        <ToggleChip label="Debris" checked={showDebris} onChange={setShowDebris} dotColor="#e8874f" />
        <ToggleChip label="Rocket bodies" checked={showRocketBodies} onChange={setShowRocketBodies} dotColor="#e8b94f" />
        <ToggleChip label="Trajectories" checked={showTrajectory} onChange={setShowTrajectory} dotColor="#4fd8c4" />
        <ToggleChip label="Conjunctions" checked={showConjunctions} onChange={setShowConjunctions} dotColor="#e85c5c" />
        {statesLoading && <span className="text-xs">Loading positions...</span>}
      </div>

      {objects.error && <ErrorState message={objects.error} />}

      <div className="relative flex-1 border border-border">
        <CesiumViewer
          markers={visibleMarkers}
          conjunctionMarkers={showConjunctions ? conjunctionMarkers : []}
          trajectoryPoints={trajectoryPoints}
          onSelect={handleSelect}
        />

        {selectedObject && (
          <div className="absolute right-4 top-4 w-72 border border-border bg-panel/95 p-4 text-sm backdrop-blur">
            <div className="mb-2 flex items-start justify-between">
              <div>
                <div className="font-medium">{selectedObject.name}</div>
                <div className="text-xs text-text-muted">NORAD {selectedObject.norad_id}</div>
              </div>
              <button
                onClick={() => handleSelect(null)}
                className="text-text-muted hover:text-text"
                aria-label="Close"
              >
                x
              </button>
            </div>
            <dl className="space-y-1 text-xs">
              <Row label="Type" value={selectedObject.object_type} />
              <Row label="Maneuverable" value={selectedObject.maneuverable ? "Yes" : "No"} />
              <Row label="Inclination" value={`${selectedObject.elements.inclination_deg.toFixed(2)} deg`} />
              <Row label="Data source" value={selectedObject.data_source} />
            </dl>
            {selectedConjunctionEvent && (
              <div className="mt-3 border-t border-border pt-3">
                <div className="mb-1 text-xs text-text-muted">Active conjunction</div>
                <SeverityBadge severity={selectedConjunctionEvent.severity} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-text-muted">{label}</dt>
      <dd className="tabular">{value}</dd>
    </div>
  );
}

function ToggleChip({
  label,
  checked,
  onChange,
  dotColor,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  dotColor: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-accent"
      />
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: dotColor }} />
      {label}
    </label>
  );
}
