"""
Two-stage conjunction detection.

Stage 1 (broad phase) is cheap and eliminates the vast majority of the
O(n^2) object pairs before any propagation happens: altitude-band overlap
(reused/extended from the original screening.py), then orbital-plane
similarity (inclination + RAAN) for the pairs that survive it.

Stage 2 (fine screening) propagates only the surviving candidate pairs over
the look-ahead window, finds the coarse closest approach, then refines the
Time of Closest Approach with a golden-section-style bisection around the
coarse minimum for better precision without a finer global time step.
"""
from __future__ import annotations

import itertools
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.db.models import TrackedObject
from app.services.propagation import Propagator
from app.services.risk import assess_risk

EARTH_RADIUS_KM = 6378.137
MU_EARTH = 398600.4418


@dataclass
class CandidatePair:
    a: TrackedObject
    b: TrackedObject


@dataclass
class ConjunctionResult:
    event_id: str
    a: TrackedObject
    b: TrackedObject
    tca: datetime
    miss_distance_km: float
    relative_velocity_km_s: float
    risk_score: float
    severity: str
    factors: dict


def _semi_major_axis_km(o: TrackedObject) -> float:
    n_rad_s = o.mean_motion_rev_per_day * 2 * math.pi / 86400.0
    return (MU_EARTH / (n_rad_s ** 2)) ** (1 / 3)


def _approx_altitude_km(o: TrackedObject) -> float:
    return _semi_major_axis_km(o) - EARTH_RADIUS_KM


def broad_phase_filter(objects: list[TrackedObject],
                        altitude_margin_km: float | None = None,
                        plane_margin_deg: float = 15.0) -> list[CandidatePair]:
    """Stage 1: cheap filters that eliminate pairs whose orbits can't
    plausibly come close, before any propagation is run.

    - Altitude bands: skip pairs whose approximate circular altitudes
      differ by more than the margin (a real conjunction needs overlapping
      radial ranges).
    - Orbital plane similarity: skip pairs whose inclination differs a lot
      *and* whose RAAN differs a lot -- very different planes rarely
      intersect within the screening window. Pairs with similar
      inclination OR similar RAAN are kept (either can still produce a
      crossing).
    """
    settings = get_settings()
    margin = altitude_margin_km or settings.broad_phase_altitude_margin_km

    # Bucket objects by altitude band for a coarse spatial partition instead
    # of a naive full pairwise comparison.
    band_width = margin
    buckets: dict[int, list[TrackedObject]] = {}
    altitudes: dict[int, float] = {}
    for o in objects:
        alt = _approx_altitude_km(o)
        altitudes[o.norad_id] = alt
        band = int(alt // band_width)
        buckets.setdefault(band, []).append(o)

    candidates: list[CandidatePair] = []
    seen_pairs: set[tuple[int, int]] = set()

    for band, members in buckets.items():
        # compare within this band and the adjacent band (objects near a
        # band boundary can still be within `margin` of each other)
        neighbor_members = buckets.get(band + 1, [])
        pool = members + neighbor_members
        for a, b in itertools.combinations(pool, 2):
            key = (min(a.norad_id, b.norad_id), max(a.norad_id, b.norad_id))
            if key in seen_pairs:
                continue
            if abs(altitudes[a.norad_id] - altitudes[b.norad_id]) > margin:
                continue

            incl_diff = abs(a.inclination_deg - b.inclination_deg)
            raan_diff = min(abs(a.raan_deg - b.raan_deg), 360 - abs(a.raan_deg - b.raan_deg))
            if incl_diff > plane_margin_deg and raan_diff > plane_margin_deg:
                continue

            seen_pairs.add(key)
            candidates.append(CandidatePair(a=a, b=b))

    return candidates


def _distance_at(propagator: Propagator, a_id: int, b_id: int, t: datetime) -> tuple[float, float]:
    sa = propagator.state_at(a_id, t)
    sb = propagator.state_at(b_id, t)
    dx = sa.position_km[0] - sb.position_km[0]
    dy = sa.position_km[1] - sb.position_km[1]
    dz = sa.position_km[2] - sb.position_km[2]
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    dvx = sa.velocity_km_s[0] - sb.velocity_km_s[0]
    dvy = sa.velocity_km_s[1] - sb.velocity_km_s[1]
    dvz = sa.velocity_km_s[2] - sb.velocity_km_s[2]
    rel_speed = math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz)
    return dist, rel_speed


def _refine_tca(propagator: Propagator, a_id: int, b_id: int,
                 coarse_t: datetime, coarse_step: timedelta,
                 iterations: int = 12) -> tuple[datetime, float, float]:
    """Ternary-search style refinement of the closest-approach time within
    +/- one coarse step around the coarse minimum."""
    lo = coarse_t - coarse_step
    hi = coarse_t + coarse_step
    best_t, best_dist, best_speed = coarse_t, *_distance_at(propagator, a_id, b_id, coarse_t)

    for _ in range(iterations):
        span = (hi - lo) / 3
        m1 = lo + span
        m2 = hi - span
        d1, s1 = _distance_at(propagator, a_id, b_id, m1)
        d2, s2 = _distance_at(propagator, a_id, b_id, m2)
        if d1 < best_dist:
            best_t, best_dist, best_speed = m1, d1, s1
        if d2 < best_dist:
            best_t, best_dist, best_speed = m2, d2, s2
        if d1 < d2:
            hi = m2
        else:
            lo = m1

    return best_t, best_dist, best_speed


def fine_screen_pair(propagator: Propagator, pair: CandidatePair,
                      start: datetime, window: timedelta, step: timedelta,
                      miss_distance_threshold_km: float) -> ConjunctionResult | None:
    n_steps = max(1, int(window / step))
    min_dist = float("inf")
    min_t = start
    min_speed = 0.0

    for i in range(n_steps + 1):
        t = start + i * step
        dist, speed = _distance_at(propagator, pair.a.norad_id, pair.b.norad_id, t)
        if dist < min_dist:
            min_dist, min_t, min_speed = dist, t, speed

    if min_dist > miss_distance_threshold_km * 3:
        # Not even close on the coarse grid -- skip the refinement cost.
        return None

    refined_t, refined_dist, refined_speed = _refine_tca(
        propagator, pair.a.norad_id, pair.b.norad_id, min_t, step
    )

    if refined_dist > miss_distance_threshold_km:
        return None

    assessment = assess_risk(
        miss_distance_km=refined_dist,
        relative_velocity_km_s=refined_speed,
        object_a=pair.a,
        object_b=pair.b,
        miss_distance_threshold_km=miss_distance_threshold_km,
    )

    return ConjunctionResult(
        event_id=f"CE-{uuid.uuid4().hex[:10].upper()}",
        a=pair.a,
        b=pair.b,
        tca=refined_t,
        miss_distance_km=round(refined_dist, 4),
        relative_velocity_km_s=round(refined_speed, 4),
        risk_score=assessment["risk_score"],
        severity=assessment["severity"],
        factors=assessment["factors"],
    )


def screen_conjunctions(objects: list[TrackedObject], propagator: Propagator,
                         window_hours: float, step_seconds: float,
                         miss_distance_threshold_km: float,
                         start_time: datetime | None = None) -> list[ConjunctionResult]:
    start_time = start_time or datetime.now(timezone.utc)
    window = timedelta(hours=window_hours)
    step = timedelta(seconds=step_seconds)

    candidates = broad_phase_filter(objects)

    results: list[ConjunctionResult] = []
    for pair in candidates:
        result = fine_screen_pair(
            propagator, pair, start_time, window, step, miss_distance_threshold_km
        )
        if result:
            results.append(result)

    return sorted(results, key=lambda r: r.risk_score, reverse=True)
