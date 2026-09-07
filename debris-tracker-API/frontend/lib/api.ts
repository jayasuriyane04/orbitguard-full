import type {
  Alert,
  AlertStatus,
  CascadeResult,
  ConjunctionEvent,
  IngestionResult,
  ManeuverCandidate,
  ObjectType,
  RemovalPriority,
  Severity,
  TrackedObject,
  Trajectory,
} from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { params?: Record<string, string | number | boolean | undefined> }
): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  if (init?.params) {
    for (const [key, value] of Object.entries(init.params)) {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const res = await fetch(url.toString(), {
    ...init,
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface ObjectFilters {
  object_type?: ObjectType;
  maneuverable?: boolean;
  min_altitude_km?: number;
  max_altitude_km?: number;
  name?: string;
  norad_id?: number;
  page?: number;
  page_size?: number;
}

export const api = {
  health: () =>
    request<{ status: string; objects_tracked: number; version: string }>(
      "/health"
    ),

  listObjects: (filters: ObjectFilters = {}) =>
    request<TrackedObject[]>("/objects", { params: { ...filters } }),

  getObject: (noradId: number) =>
    request<TrackedObject>(`/objects/${noradId}`),

  getState: (noradId: number, at?: string) =>
    request<import("@/types/api").StateVector>(`/objects/${noradId}/state`, {
      params: { at },
    }),

  getTrajectory: (noradId: number, durationHours = 2, stepSeconds = 60) =>
    request<Trajectory>(`/objects/${noradId}/trajectory`, {
      params: { duration_hours: durationHours, step_seconds: stepSeconds },
    }),

  refreshIngestion: () =>
    request<IngestionResult>("/ingestion/refresh", { method: "POST" }),

  screenConjunctions: (body: {
    window_hours: number;
    step_seconds: number;
    miss_distance_threshold_km: number;
    persist: boolean;
  }) =>
    request<ConjunctionEvent[]>("/conjunctions/screen", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listConjunctions: (filters: {
    severity?: Severity;
    norad_id?: number;
    page?: number;
    page_size?: number;
  } = {}) =>
    request<ConjunctionEvent[]>("/conjunctions", { params: { ...filters } }),

  getConjunction: (eventId: string) =>
    request<ConjunctionEvent>(`/conjunctions/${eventId}`),

  generateManeuver: (
    eventId: string,
    body: { maneuvering_norad_id?: number; delta_v_candidates_m_s?: number[] } = {}
  ) =>
    request<ManeuverCandidate[]>(`/conjunctions/${eventId}/maneuver`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getRemovalPriorities: () =>
    request<RemovalPriority[]>("/debris/priorities"),

  simulateCascade: (body: {
    event_id: string;
    fragment_count: number;
    simulation_hours: number;
  }) =>
    request<CascadeResult>("/cascade/simulate", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listAlerts: (filters: { status?: AlertStatus; page?: number; page_size?: number } = {}) =>
    request<Alert[]>("/alerts", { params: { ...filters } }),

  acknowledgeAlert: (alertId: number) =>
    request<Alert>(`/alerts/${alertId}/acknowledge`, { method: "PATCH" }),
};
