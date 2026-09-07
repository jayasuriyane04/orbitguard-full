"use client";

import { useState } from "react";
import { Waves } from "lucide-react";

import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { PageHeader, Panel, LoadingState, ErrorState, EmptyState } from "@/components/Panel";
import type { CascadeResult } from "@/types/api";

export default function CascadeSimulatorPage() {
  const [eventId, setEventId] = useState("");
  const [fragmentCount, setFragmentCount] = useState(20);
  const [simulationHours, setSimulationHours] = useState(48);
  const [result, setResult] = useState<CascadeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recentEvents = useApiData(() => api.listConjunctions({ page_size: 20 }));

  async function runSimulation() {
    if (!eventId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.simulateCascade({
        event_id: eventId,
        fragment_count: fragmentCount,
        simulation_hours: simulationHours,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Cascade simulator"
        description="Educational / decision-support simulation only -- not a scientific-grade long-term debris environment model."
      />

      <Panel title="Scenario setup" className="mb-6">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="mb-1 block text-xs text-text-muted">Conjunction event</label>
            <select
              value={eventId}
              onChange={(e) => setEventId(e.target.value)}
              className="w-72 border border-border bg-panel px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              <option value="">Select an event</option>
              {recentEvents.data?.map((e) => (
                <option key={e.event_id} value={e.event_id}>
                  {e.event_id} -- {e.primary_object_name} / {e.secondary_object_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Fragment count</label>
            <input
              type="number"
              min={1}
              max={200}
              value={fragmentCount}
              onChange={(e) => setFragmentCount(Number(e.target.value))}
              className="w-28 border border-border bg-panel px-3 py-1.5 text-sm tabular focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Simulation period (hours)</label>
            <input
              type="number"
              min={1}
              max={720}
              value={simulationHours}
              onChange={(e) => setSimulationHours(Number(e.target.value))}
              className="w-28 border border-border bg-panel px-3 py-1.5 text-sm tabular focus:border-accent focus:outline-none"
            />
          </div>
          <button
            onClick={runSimulation}
            disabled={!eventId || loading}
            className="flex items-center gap-2 border border-accent px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-50"
          >
            <Waves size={14} />
            {loading ? "Simulating..." : "Run simulation"}
          </button>
        </div>
      </Panel>

      {error && <ErrorState message={error} />}

      {loading && <LoadingState label="Running cascade simulation" />}

      {result && (
        <>
          <div className="mb-3 text-xs text-text-muted">{result.disclaimer}</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Panel title="No intervention">
              <ScenarioStats
                fragments={result.without_intervention.fragment_count}
                conjunctions={result.without_intervention.new_conjunctions}
                highRisk={result.without_intervention.high_risk_events}
              />
            </Panel>
            <Panel title="With avoidance">
              <ScenarioStats
                fragments={result.with_avoidance.fragment_count}
                conjunctions={result.with_avoidance.new_conjunctions}
                highRisk={result.with_avoidance.high_risk_events}
              />
            </Panel>
            <Panel title="With debris removal">
              <ScenarioStats
                fragments={result.with_removal.fragment_count}
                conjunctions={result.with_removal.new_conjunctions}
                highRisk={result.with_removal.high_risk_events}
              />
            </Panel>
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <EmptyState message="Select a conjunction event above and run a simulation." />
      )}
    </div>
  );
}

function ScenarioStats({
  fragments,
  conjunctions,
  highRisk,
}: {
  fragments: number;
  conjunctions: number;
  highRisk: number;
}) {
  return (
    <dl className="space-y-3 text-sm">
      <div className="flex justify-between">
        <dt className="text-text-muted">Fragments generated</dt>
        <dd className="tabular">{fragments}</dd>
      </div>
      <div className="flex justify-between">
        <dt className="text-text-muted">New close approaches</dt>
        <dd className="tabular">{conjunctions}</dd>
      </div>
      <div className="flex justify-between">
        <dt className="text-text-muted">High-risk events</dt>
        <dd className="tabular text-severity-high">{highRisk}</dd>
      </div>
    </dl>
  );
}
