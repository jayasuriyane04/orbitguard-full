"use client";

import { useState } from "react";
import Link from "next/link";

import { api, type ObjectFilters } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { approxAltitudeKm } from "@/lib/orbital";
import { PageHeader, Panel, LoadingState, ErrorState, EmptyState } from "@/components/Panel";
import type { ObjectType } from "@/types/api";

const OBJECT_TYPES: { value: ObjectType | ""; label: string }[] = [
  { value: "", label: "All types" },
  { value: "ACTIVE_SATELLITE", label: "Active satellites" },
  { value: "DEBRIS", label: "Debris" },
  { value: "ROCKET_BODY", label: "Rocket bodies" },
  { value: "UNKNOWN", label: "Unknown" },
];

export default function ObjectsPage() {
  const [nameFilter, setNameFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<ObjectType | "">("");
  const [maneuverableOnly, setManeuverableOnly] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const filters: ObjectFilters = {
    page,
    page_size: pageSize,
    ...(nameFilter ? { name: nameFilter } : {}),
    ...(typeFilter ? { object_type: typeFilter } : {}),
    ...(maneuverableOnly ? { maneuverable: true } : {}),
  };

  const objects = useApiData(
    () => api.listObjects(filters),
    [nameFilter, typeFilter, maneuverableOnly, page]
  );

  return (
    <div>
      <PageHeader
        title="Objects"
        description="Tracked catalog: satellites, debris, and rocket bodies with current orbital elements."
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          value={nameFilter}
          onChange={(e) => {
            setPage(1);
            setNameFilter(e.target.value);
          }}
          placeholder="Search by name"
          className="border border-border bg-panel px-3 py-1.5 text-sm text-text placeholder:text-text-muted focus:border-accent focus:outline-none"
        />
        <select
          value={typeFilter}
          onChange={(e) => {
            setPage(1);
            setTypeFilter(e.target.value as ObjectType | "");
          }}
          className="border border-border bg-panel px-3 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
        >
          {OBJECT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-text-muted">
          <input
            type="checkbox"
            checked={maneuverableOnly}
            onChange={(e) => {
              setPage(1);
              setManeuverableOnly(e.target.checked);
            }}
            className="accent-accent"
          />
          Maneuverable only
        </label>
      </div>

      <Panel>
        {objects.loading ? (
          <LoadingState />
        ) : objects.error ? (
          <ErrorState message={objects.error} />
        ) : !objects.data || objects.data.length === 0 ? (
          <EmptyState message="No objects match these filters." />
        ) : (
          <>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-text-muted">
                  <th className="pb-2 font-normal">NORAD ID</th>
                  <th className="pb-2 font-normal">Name</th>
                  <th className="pb-2 font-normal">Type</th>
                  <th className="pb-2 font-normal">Approx. altitude</th>
                  <th className="pb-2 font-normal">Inclination</th>
                  <th className="pb-2 font-normal">Maneuverable</th>
                  <th className="pb-2 font-normal">Source</th>
                </tr>
              </thead>
              <tbody>
                {objects.data.map((o) => (
                  <tr key={o.norad_id} className="border-b border-border/60 last:border-0">
                    <td className="py-2 tabular">
                      <Link href={`/objects/${o.norad_id}`} className="text-accent hover:underline">
                        {o.norad_id}
                      </Link>
                    </td>
                    <td className="py-2">{o.name}</td>
                    <td className="py-2 text-text-muted">{o.object_type}</td>
                    <td className="py-2 tabular">{approxAltitudeKm(o).toFixed(0)} km</td>
                    <td className="py-2 tabular">{o.elements.inclination_deg.toFixed(2)} deg</td>
                    <td className="py-2">{o.maneuverable ? "Yes" : "No"}</td>
                    <td className="py-2 text-text-muted">{o.data_source}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="mt-4 flex items-center justify-between text-xs text-text-muted">
              <span>Page {page}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="border border-border px-3 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={objects.data.length < pageSize}
                  className="border border-border px-3 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
