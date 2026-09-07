"""
Persistent database schema.

Replaces the previous in-memory-only catalog. TrackedObject is the object
registry; OrbitalState is a small cache of recent propagation results;
ConjunctionEvent / ManeuverRecommendation / RemovalPriority / Alert record
the outputs of the analysis pipeline so the API and dashboard can query
history rather than recomputing everything on every request.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.schemas.enums import (
    AlertStatus,
    ManeuverDirection,
    ObjectType,
    Severity,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrackedObject(Base):
    __tablename__ = "tracked_objects"
    __table_args__ = (
        UniqueConstraint("norad_id", name="uq_tracked_objects_norad_id"),
        Index("ix_tracked_objects_object_type", "object_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    norad_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[ObjectType] = mapped_column(SAEnum(ObjectType), nullable=False)

    # TLE / element source data
    tle_line1: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tle_line2: Mapped[str | None] = mapped_column(String(80), nullable=True)
    epoch: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inclination_deg: Mapped[float] = mapped_column(Float, nullable=False)
    eccentricity: Mapped[float] = mapped_column(Float, nullable=False)
    raan_deg: Mapped[float] = mapped_column(Float, nullable=False)
    arg_perigee_deg: Mapped[float] = mapped_column(Float, nullable=False)
    mean_anomaly_deg: Mapped[float] = mapped_column(Float, nullable=False)
    mean_motion_rev_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    bstar: Mapped[float] = mapped_column(Float, default=0.0)

    rcs_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    maneuverable: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    data_source: Mapped[str] = mapped_column(String(32), default="SYNTHETIC")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    states: Mapped[list["OrbitalState"]] = relationship(
        back_populates="object", cascade="all, delete-orphan"
    )


class OrbitalState(Base):
    """A cached propagated state vector at a specific timestamp.

    This is a cache, not the source of truth for orbit determination --
    it lets repeated requests for the same (object, time) avoid re-running
    SGP4, and gives the dashboard a lightweight history table to query.
    """

    __tablename__ = "orbital_states"
    __table_args__ = (
        Index("ix_orbital_states_object_time", "tracked_object_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracked_object_id: Mapped[int] = mapped_column(
        ForeignKey("tracked_objects.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    x_km: Mapped[float] = mapped_column(Float)
    y_km: Mapped[float] = mapped_column(Float)
    z_km: Mapped[float] = mapped_column(Float)
    vx_km_s: Mapped[float] = mapped_column(Float)
    vy_km_s: Mapped[float] = mapped_column(Float)
    vz_km_s: Mapped[float] = mapped_column(Float)
    altitude_km: Mapped[float] = mapped_column(Float)
    latitude_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude_deg: Mapped[float | None] = mapped_column(Float, nullable=True)

    object: Mapped["TrackedObject"] = relationship(back_populates="states")


class ConjunctionEvent(Base):
    __tablename__ = "conjunction_events"
    __table_args__ = (Index("ix_conjunction_events_severity", "severity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    primary_object_norad_id: Mapped[int] = mapped_column(Integer, nullable=False)
    secondary_object_norad_id: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_object_name: Mapped[str] = mapped_column(String(128))
    secondary_object_name: Mapped[str] = mapped_column(String(128))

    tca: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    miss_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity_km_s: Mapped[float] = mapped_column(Float, nullable=False)

    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[Severity] = mapped_column(SAEnum(Severity), nullable=False)
    risk_factors_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    maneuvers: Mapped[list["ManeuverRecommendation"]] = relationship(
        back_populates="conjunction", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="conjunction", cascade="all, delete-orphan"
    )


class ManeuverRecommendation(Base):
    __tablename__ = "maneuver_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conjunction_id: Mapped[int] = mapped_column(
        ForeignKey("conjunction_events.id", ondelete="CASCADE"), nullable=False
    )
    maneuvering_object_norad_id: Mapped[int] = mapped_column(Integer, nullable=False)

    direction: Mapped[ManeuverDirection] = mapped_column(SAEnum(ManeuverDirection))
    delta_v_m_s: Mapped[float] = mapped_column(Float)
    execute_before_tca_minutes: Mapped[float] = mapped_column(Float)

    original_miss_distance_km: Mapped[float] = mapped_column(Float)
    predicted_miss_distance_km: Mapped[float] = mapped_column(Float)
    original_risk_score: Mapped[float] = mapped_column(Float)
    predicted_risk_score: Mapped[float] = mapped_column(Float)

    is_decision_support_only: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conjunction: Mapped["ConjunctionEvent"] = relationship(back_populates="maneuvers")


class RemovalPriority(Base):
    __tablename__ = "removal_priorities"
    __table_args__ = (UniqueConstraint("norad_id", name="uq_removal_priority_norad_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    norad_id: Mapped[int] = mapped_column(Integer, nullable=False)
    object_name: Mapped[str] = mapped_column(String(128))

    removal_priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    conjunction_count: Mapped[int] = mapped_column(Integer, default=0)
    average_severity_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conjunction_id: Mapped[int | None] = mapped_column(
        ForeignKey("conjunction_events.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[Severity] = mapped_column(SAEnum(Severity), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus), default=AlertStatus.NEW, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conjunction: Mapped["ConjunctionEvent | None"] = relationship(back_populates="alerts")
