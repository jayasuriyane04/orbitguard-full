from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import ObjectType


class OrbitalElements(BaseModel):
    """Classical (Keplerian) orbital elements used to initialize SGP4."""

    model_config = ConfigDict(frozen=True)

    inclination_deg: float = Field(..., ge=0, le=180)
    raan_deg: float = Field(..., ge=0, lt=360)
    eccentricity: float = Field(..., ge=0, lt=1)
    arg_perigee_deg: float = Field(..., ge=0, lt=360)
    mean_anomaly_deg: float = Field(..., ge=0, lt=360)
    mean_motion_rev_per_day: float = Field(..., gt=0)
    bstar: float = 0.0


class TrackedObjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    norad_id: int
    name: str
    object_type: ObjectType
    tle_line1: str | None = None
    tle_line2: str | None = None
    epoch: datetime
    elements: OrbitalElements = Field(
        ..., description="Populated from the row's orbital element columns"
    )
    rcs_m2: float | None = None
    maneuverable: bool
    active: bool
    data_source: str

    @classmethod
    def from_orm_row(cls, row) -> "TrackedObjectOut":
        return cls(
            norad_id=row.norad_id,
            name=row.name,
            object_type=row.object_type,
            tle_line1=row.tle_line1,
            tle_line2=row.tle_line2,
            epoch=row.epoch,
            elements=OrbitalElements(
                inclination_deg=row.inclination_deg,
                raan_deg=row.raan_deg,
                eccentricity=row.eccentricity,
                arg_perigee_deg=row.arg_perigee_deg,
                mean_anomaly_deg=row.mean_anomaly_deg,
                mean_motion_rev_per_day=row.mean_motion_rev_per_day,
                bstar=row.bstar,
            ),
            rcs_m2=row.rcs_m2,
            maneuverable=row.maneuverable,
            active=row.active,
            data_source=row.data_source,
        )


class StateVectorOut(BaseModel):
    norad_id: int
    timestamp: datetime
    x_km: float
    y_km: float
    z_km: float
    vx_km_s: float
    vy_km_s: float
    vz_km_s: float
    altitude_km: float
    latitude_deg: float | None = None
    longitude_deg: float | None = None


class TrajectoryPoint(BaseModel):
    timestamp: datetime
    x_km: float
    y_km: float
    z_km: float
    vx_km_s: float
    vy_km_s: float
    vz_km_s: float
    latitude_deg: float | None = None
    longitude_deg: float | None = None
    altitude_km: float | None = None


class TrajectoryOut(BaseModel):
    norad_id: int
    start: datetime
    end: datetime
    step_seconds: float
    points: list[TrajectoryPoint]


class IngestionResult(BaseModel):
    source: str
    fetched: int
    created: int
    updated: int
    skipped_invalid: int
    used_fallback: bool
    last_update: datetime
