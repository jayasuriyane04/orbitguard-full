export type ObjectType =
  | "ACTIVE_SATELLITE"
  | "DEBRIS"
  | "ROCKET_BODY"
  | "UNKNOWN";

export type Severity = "LOW" | "MODERATE" | "HIGH" | "CRITICAL";

export type AlertStatus = "NEW" | "ACKNOWLEDGED" | "RESOLVED";

export type ManeuverDirection =
  | "PROGRADE"
  | "RETROGRADE"
  | "RADIAL_OUTWARD"
  | "RADIAL_INWARD"
  | "NORMAL"
  | "ANTI_NORMAL";

export interface OrbitalElements {
  inclination_deg: number;
  raan_deg: number;
  eccentricity: number;
  arg_perigee_deg: number;
  mean_anomaly_deg: number;
  mean_motion_rev_per_day: number;
  bstar: number;
}

export interface TrackedObject {
  norad_id: number;
  name: string;
  object_type: ObjectType;
  tle_line1: string | null;
  tle_line2: string | null;
  epoch: string;
  elements: OrbitalElements;
  rcs_m2: number | null;
  maneuverable: boolean;
  active: boolean;
  data_source: string;
}

export interface StateVector {
  norad_id: number;
  timestamp: string;
  x_km: number;
  y_km: number;
  z_km: number;
  vx_km_s: number;
  vy_km_s: number;
  vz_km_s: number;
  altitude_km: number;
  latitude_deg: number | null;
  longitude_deg: number | null;
}

export interface TrajectoryPoint {
  timestamp: string;
  x_km: number;
  y_km: number;
  z_km: number;
  vx_km_s: number;
  vy_km_s: number;
  vz_km_s: number;
  latitude_deg: number | null;
  longitude_deg: number | null;
  altitude_km: number | null;
}

export interface Trajectory {
  norad_id: number;
  start: string;
  end: string;
  step_seconds: number;
  points: TrajectoryPoint[];
}

export interface RiskFactors {
  distance: number;
  velocity: number;
  object_type: number;
  maneuverability: number;
}

export interface ConjunctionEvent {
  event_id: string;
  primary_object: number;
  secondary_object: number;
  primary_object_name: string;
  secondary_object_name: string;
  tca: string;
  miss_distance_km: number;
  relative_velocity_km_s: number;
  risk_score: number;
  severity: Severity;
  factors: RiskFactors | null;
  created_at: string;
}

export interface ManeuverCandidate {
  direction: ManeuverDirection;
  delta_v_m_s: number;
  execute_before_tca_minutes: number;
  original_miss_distance_km: number;
  predicted_miss_distance_km: number;
  original_risk_score: number;
  predicted_risk_score: number;
  note: string;
}

export interface RemovalPriority {
  norad_id: number;
  object_name: string;
  removal_priority_score: number;
  conjunction_count: number;
  average_severity_score: number;
  explanation: string | null;
}

export interface CascadeScenario {
  label: string;
  fragment_count: number;
  simulated_hours: number;
  new_conjunctions: number;
  high_risk_events: number;
}

export interface CascadeResult {
  event_id: string;
  disclaimer: string;
  without_intervention: CascadeScenario;
  with_avoidance: CascadeScenario;
  with_removal: CascadeScenario;
}

export interface Alert {
  id: number;
  conjunction_db_id: number | null;
  severity: Severity;
  title: string;
  message: string;
  status: AlertStatus;
  created_at: string;
}

export interface IngestionResult {
  source: string;
  fetched: number;
  created: number;
  updated: number;
  skipped_invalid: number;
  used_fallback: boolean;
  last_update: string;
}
