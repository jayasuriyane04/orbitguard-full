"""
Kessler-cascade simulator (educational / decision-support only).

Given a selected conjunction, models what happens if the collision were to
actually occur: a configurable number of representative fragments are
generated at the collision point with randomized velocity perturbations,
propagated forward (two-body, short horizon) alongside the existing
catalog, and the resulting extra close-approaches are counted. This is
explicitly NOT a scientific-grade long-term debris-environment model (a
real one, e.g. NASA's LEGEND/DAS or ESA's MASTER, models atmospheric decay,
fragment size-velocity distributions from hypervelocity impact testing,
and multi-year evolution) -- it exists to make the *shape* of cascading
risk visible for a demo, and to compare three mitigation postures.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.db.models import TrackedObject
from app.services.propagation import Propagator
from app.services.twobody import propagate_two_body

DISCLAIMER = (
    "Educational / decision-support simulation only -- not a scientific-grade "
    "long-term debris environment model."
)


@dataclass
class ScenarioResult:
    label: str
    fragment_count: int
    simulated_hours: float
    new_conjunctions: int
    high_risk_events: int


def _generate_fragments(
    r0: tuple[float, float, float], v0: tuple[float, float, float],
    count: int, max_delta_v_km_s: float = 0.5, seed: int | None = None,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    rng = random.Random(seed)
    fragments = []
    for _ in range(count):
        dv = (
            rng.uniform(-max_delta_v_km_s, max_delta_v_km_s),
            rng.uniform(-max_delta_v_km_s, max_delta_v_km_s),
            rng.uniform(-max_delta_v_km_s, max_delta_v_km_s),
        )
        v_frag = tuple(v0[i] + dv[i] for i in range(3))
        fragments.append((r0, v_frag))
    return fragments


def _count_close_approaches(
    fragments: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    start_time: datetime, hours: float,
    background: Propagator, background_ids: list[int],
    threshold_km: float = 25.0, high_risk_threshold_km: float = 5.0,
    step_minutes: float = 10.0,
) -> tuple[int, int]:
    """Count how many (fragment, background object) pairs come within
    threshold_km at least once over the simulated period."""
    total_close = 0
    high_risk = 0
    step = timedelta(minutes=step_minutes)
    n_steps = max(1, int((hours * 60) / step_minutes))

    # Sample a subset of background objects for performance if the catalog
    # is large -- this is a demo-scale simulation, not a production
    # screening pass.
    sample_ids = background_ids[:60]

    for r0, v0 in fragments:
        min_dist_per_bg: dict[int, float] = {bg_id: float("inf") for bg_id in sample_ids}
        for step_idx in range(n_steps + 1):
            t = start_time + step_idx * step
            dt = (t - start_time).total_seconds()
            try:
                r_f, _ = propagate_two_body(r0, v0, dt)
            except Exception:  # noqa: BLE001 - degenerate two-body edge case
                break
            for bg_id in sample_ids:
                try:
                    s_bg = background.state_at(bg_id, t)
                except (KeyError, ValueError):
                    continue
                dx = r_f[0] - s_bg.position_km[0]
                dy = r_f[1] - s_bg.position_km[1]
                dz = r_f[2] - s_bg.position_km[2]
                dist = (dx * dx + dy * dy + dz * dz) ** 0.5
                if dist < min_dist_per_bg[bg_id]:
                    min_dist_per_bg[bg_id] = dist

        for dist in min_dist_per_bg.values():
            if dist <= threshold_km:
                total_close += 1
            if dist <= high_risk_threshold_km:
                high_risk += 1

    return total_close, high_risk


def simulate_cascade(
    propagator: Propagator,
    primary: TrackedObject,
    secondary: TrackedObject,
    tca: datetime,
    catalog: list[TrackedObject],
    fragment_count: int = 20,
    simulation_hours: float = 48.0,
    seed: int | None = 7,
) -> dict[str, ScenarioResult]:
    state = propagator.state_at(primary.norad_id, tca)
    background_ids = [o.norad_id for o in catalog
                       if o.norad_id not in (primary.norad_id, secondary.norad_id)]

    # --- Scenario 1: no intervention -- collision happens, fragments spread ---
    fragments = _generate_fragments(state.position_km, state.velocity_km_s,
                                     fragment_count, seed=seed)
    close_n, high_n = _count_close_approaches(
        fragments, tca, simulation_hours, propagator, background_ids
    )
    without_intervention = ScenarioResult(
        label="NO_INTERVENTION", fragment_count=fragment_count,
        simulated_hours=simulation_hours, new_conjunctions=close_n, high_risk_events=high_n,
    )

    # --- Scenario 2: avoidance succeeds -- no collision, no new fragments ---
    with_avoidance = ScenarioResult(
        label="AVOIDANCE", fragment_count=0,
        simulated_hours=simulation_hours, new_conjunctions=0, high_risk_events=0,
    )

    # --- Scenario 3: the debris object is removed beforehand -- collision
    # cannot occur because one of the two bodies no longer exists in orbit.
    with_removal = ScenarioResult(
        label="REMOVAL", fragment_count=0,
        simulated_hours=simulation_hours, new_conjunctions=0, high_risk_events=0,
    )

    return {
        "without_intervention": without_intervention,
        "with_avoidance": with_avoidance,
        "with_removal": with_removal,
    }
