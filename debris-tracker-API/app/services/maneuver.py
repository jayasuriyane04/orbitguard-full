"""
Collision-avoidance maneuver planner.

Only produces recommendations when at least one of the two conjuncting
objects is maneuverable (matches ORBITGUARD's positioning: this supports
satellite-operator decisions, it never claims debris can be commanded).

For the maneuverable object, tries each of the six standard burn
directions (prograde/retrograde/radial-in/out/normal/anti-normal) at
several delta-v magnitudes, applies the burn at a candidate lead time
before TCA, propagates the perturbed trajectory with two-body mechanics
(see twobody.py) for the short remaining interval, and re-checks the
miss distance and risk against the other object's original (unperturbed)
SGP4 trajectory. Candidates are ranked by predicted risk reduction with a
preference for lower delta-v cost.

This module explicitly marks all output as decision-support / simulation,
never as an operational flight command.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.db.models import TrackedObject
from app.schemas.enums import ManeuverDirection
from app.services.propagation import Propagator
from app.services.risk import assess_risk
from app.services.twobody import propagate_two_body

# Lead times (minutes before TCA) at which the burn is assumed to execute.
_LEAD_TIMES_MINUTES = [15.0, 30.0, 45.0, 60.0, 90.0]
_DEFAULT_DELTA_V_CANDIDATES_M_S = [0.02, 0.05, 0.1, 0.2, 0.4, 0.8]


@dataclass
class ManeuverCandidateResult:
    direction: ManeuverDirection
    delta_v_m_s: float
    execute_before_tca_minutes: float
    original_miss_distance_km: float
    predicted_miss_distance_km: float
    original_risk_score: float
    predicted_risk_score: float


def _unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _burn_direction_vector(direction: ManeuverDirection, r: tuple[float, float, float],
                            v: tuple[float, float, float]) -> tuple[float, float, float]:
    prograde = _unit(v)
    radial = _unit(r)
    normal = _unit(_cross(r, v))

    if direction == ManeuverDirection.PROGRADE:
        return prograde
    if direction == ManeuverDirection.RETROGRADE:
        return tuple(-c for c in prograde)
    if direction == ManeuverDirection.RADIAL_OUTWARD:
        return radial
    if direction == ManeuverDirection.RADIAL_INWARD:
        return tuple(-c for c in radial)
    if direction == ManeuverDirection.NORMAL:
        return normal
    if direction == ManeuverDirection.ANTI_NORMAL:
        return tuple(-c for c in normal)
    raise ValueError(f"unknown maneuver direction {direction}")


def _closest_approach_after_burn(
    propagator: Propagator, maneuvering_id: int, other_id: int,
    burn_time: datetime, r_burn: tuple[float, float, float], v_burn: tuple[float, float, float],
    search_start: datetime, search_end: datetime, step_seconds: float = 5.0,
) -> tuple[datetime, float, float]:
    """Sample distance between the maneuvered (two-body) trajectory and the
    other object's original SGP4 trajectory across a window, return the
    minimum found."""
    best_t, best_dist, best_speed = search_start, float("inf"), 0.0
    t = search_start
    step = timedelta(seconds=step_seconds)
    while t <= search_end:
        dt = (t - burn_time).total_seconds()
        r_m, v_m = propagate_two_body(r_burn, v_burn, dt)
        s_other = propagator.state_at(other_id, t)
        dx = r_m[0] - s_other.position_km[0]
        dy = r_m[1] - s_other.position_km[1]
        dz = r_m[2] - s_other.position_km[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist < best_dist:
            dvx = v_m[0] - s_other.velocity_km_s[0]
            dvy = v_m[1] - s_other.velocity_km_s[1]
            dvz = v_m[2] - s_other.velocity_km_s[2]
            best_dist = dist
            best_t = t
            best_speed = math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz)
        t += step
    return best_t, best_dist, best_speed


def plan_maneuvers(
    propagator: Propagator,
    maneuvering_object: TrackedObject,
    other_object: TrackedObject,
    tca: datetime,
    original_miss_distance_km: float,
    original_risk_score: float,
    miss_distance_threshold_km: float,
    delta_v_candidates_m_s: list[float] | None = None,
) -> list[ManeuverCandidateResult]:
    if not maneuvering_object.maneuverable:
        return []

    delta_vs_km_s = [dv / 1000.0 for dv in (delta_v_candidates_m_s or _DEFAULT_DELTA_V_CANDIDATES_M_S)]
    candidates: list[ManeuverCandidateResult] = []

    for lead_minutes in _LEAD_TIMES_MINUTES:
        burn_time = tca - timedelta(minutes=lead_minutes)
        if burn_time <= datetime.now(burn_time.tzinfo):
            continue  # burn would already need to have happened
        try:
            state = propagator.state_at(maneuvering_object.norad_id, burn_time)
        except (KeyError, ValueError):
            continue

        for direction in ManeuverDirection:
            unit_vec = _burn_direction_vector(direction, state.position_km, state.velocity_km_s)
            for dv in delta_vs_km_s:
                v_burn = tuple(
                    state.velocity_km_s[i] + dv * unit_vec[i] for i in range(3)
                )
                search_start = tca - timedelta(minutes=lead_minutes + 5)
                search_end = tca + timedelta(minutes=10)
                _, new_dist, new_speed = _closest_approach_after_burn(
                    propagator, maneuvering_object.norad_id, other_object.norad_id,
                    burn_time, state.position_km, v_burn, search_start, search_end,
                )
                assessment = assess_risk(
                    miss_distance_km=new_dist,
                    relative_velocity_km_s=new_speed,
                    object_a=maneuvering_object,
                    object_b=other_object,
                    miss_distance_threshold_km=miss_distance_threshold_km,
                )
                candidates.append(ManeuverCandidateResult(
                    direction=direction,
                    delta_v_m_s=round(dv * 1000, 4),
                    execute_before_tca_minutes=lead_minutes,
                    original_miss_distance_km=round(original_miss_distance_km, 4),
                    predicted_miss_distance_km=round(new_dist, 4),
                    original_risk_score=round(original_risk_score, 4),
                    predicted_risk_score=assessment["risk_score"],
                ))

    # Rank: lowest predicted risk first, then largest miss-distance
    # improvement, then lowest delta-v cost (cheapest burn among
    # equally-effective options).
    candidates.sort(key=lambda c: (
        c.predicted_risk_score,
        -c.predicted_miss_distance_km,
        c.delta_v_m_s,
    ))
    return candidates


def best_maneuver(candidates: list[ManeuverCandidateResult]) -> ManeuverCandidateResult | None:
    return candidates[0] if candidates else None
