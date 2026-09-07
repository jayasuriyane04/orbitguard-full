from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AlertStatus, ManeuverDirection, Severity


class RiskFactors(BaseModel):
    distance: float = Field(..., ge=0, le=1)
    velocity: float = Field(..., ge=0, le=1)
    object_type: float = Field(..., ge=0, le=1)
    maneuverability: float = Field(..., ge=0, le=1)


class ConjunctionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    event_id: str
    primary_object: int = Field(..., validation_alias="primary_object_norad_id")
    secondary_object: int = Field(..., validation_alias="secondary_object_norad_id")
    primary_object_name: str
    secondary_object_name: str
    tca: datetime
    miss_distance_km: float
    relative_velocity_km_s: float
    risk_score: float
    severity: Severity
    factors: RiskFactors | None = None
    created_at: datetime


class ScreeningRequest(BaseModel):
    window_hours: float = Field(24.0, gt=0, le=168)
    step_seconds: float = Field(30.0, gt=0, le=300)
    miss_distance_threshold_km: float = Field(25.0, gt=0, le=500)
    persist: bool = Field(True, description="Store resulting events + trigger alerts")


class ManeuverCandidate(BaseModel):
    direction: ManeuverDirection
    delta_v_m_s: float
    execute_before_tca_minutes: float
    original_miss_distance_km: float
    predicted_miss_distance_km: float
    original_risk_score: float
    predicted_risk_score: float
    note: str = "Decision-support simulation output, not an operational flight command."


class ManeuverRequest(BaseModel):
    maneuvering_norad_id: int | None = Field(
        None, description="Which object to maneuver; defaults to the maneuverable one"
    )
    delta_v_candidates_m_s: list[float] = Field(
        default_factory=lambda: [0.05, 0.1, 0.2, 0.4, 0.8]
    )


class RemovalPriorityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    norad_id: int
    object_name: str
    removal_priority_score: float
    conjunction_count: int
    average_severity_score: float
    explanation: str | None = None


class CascadeScenario(BaseModel):
    label: str
    fragment_count: int
    simulated_hours: float
    new_conjunctions: int
    high_risk_events: int


class CascadeRequest(BaseModel):
    event_id: str
    fragment_count: int = Field(20, ge=1, le=200)
    simulation_hours: float = Field(48.0, gt=0, le=720)


class CascadeResult(BaseModel):
    event_id: str
    disclaimer: str = (
        "Educational / decision-support simulation only -- not a "
        "scientific-grade long-term debris environment model."
    )
    without_intervention: CascadeScenario
    with_avoidance: CascadeScenario
    with_removal: CascadeScenario


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    conjunction_db_id: int | None = Field(None, validation_alias="conjunction_id")
    severity: Severity
    title: str
    message: str
    status: AlertStatus
    created_at: datetime
