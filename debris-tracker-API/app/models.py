from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class ObjectType(str, Enum):
    satellite = "satellite"
    debris = "debris"
    rocket_body = "rocket_body"


class OrbitalElements(BaseModel):
    """Classical (Keplerian) orbital elements used to initialize SGP4."""
    model_config = ConfigDict(frozen=True)

    inclination_deg: float = Field(..., ge=0, le=180)
    raan_deg: float = Field(..., ge=0, lt=360, description="Right ascension of ascending node")
    eccentricity: float = Field(..., ge=0, lt=1)
    arg_perigee_deg: float = Field(..., ge=0, lt=360)
    mean_anomaly_deg: float = Field(..., ge=0, lt=360)
    mean_motion_rev_per_day: float = Field(..., gt=0)
    bstar: float = Field(0.0, description="Drag term")


class TrackedObject(BaseModel):
    norad_id: int
    name: str
    object_type: ObjectType
    rcs_m2: float = Field(..., gt=0, description="Radar cross-section, proxy for physical size")
    maneuverable: bool
    elements: OrbitalElements
    epoch: datetime


class StateVector(BaseModel):
    norad_id: int
    epoch: datetime
    position_km: tuple[float, float, float]
    velocity_km_s: tuple[float, float, float]
    altitude_km: float


class RiskLevel(str, Enum):
    monitor = "monitor"
    elevated = "elevated"
    critical = "critical"


class ConjunctionEvent(BaseModel):
    object_a: int
    object_b: int
    object_a_name: str
    object_b_name: str
    time_of_closest_approach: datetime
    miss_distance_km: float
    relative_speed_km_s: float
    probability_of_collision: float = Field(..., ge=0, le=1, description="Simplified heuristic estimate, not a certified Pc")
    risk_level: RiskLevel
    recommended_action: str


class ScreeningRequest(BaseModel):
    window_hours: float = Field(3.0, gt=0, le=72, description="Look-ahead window for screening")
    step_seconds: float = Field(15.0, gt=0, le=300, description="Coarse sampling interval")
    miss_distance_threshold_km: float = Field(25.0, gt=0, le=200)
