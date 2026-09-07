"""
Minimal two-body (Keplerian) propagator using the universal-variable
formulation (Curtis, "Orbital Mechanics for Engineering Students").

Used ONLY for short-horizon "what if we burned here" maneuver simulation:
SGP4 has no notion of "add this delta-v to the velocity and keep going", so
after applying a candidate burn we propagate the perturbed state with plain
two-body mechanics for the (short, minutes-to-hours) remaining time to the
conjunction. This ignores drag/J2 over that short horizon, which is a
reasonable approximation for a decision-support estimate but is explicitly
NOT a substitute for a real maneuver-planning tool's precision propagation.
"""
from __future__ import annotations

import math

MU_EARTH = 398600.4418  # km^3/s^2


def _stumpff_c(z: float) -> float:
    if z > 1e-8:
        return (1 - math.cos(math.sqrt(z))) / z
    if z < -1e-8:
        return (math.cosh(math.sqrt(-z)) - 1) / (-z)
    return 0.5


def _stumpff_s(z: float) -> float:
    if z > 1e-8:
        sz = math.sqrt(z)
        return (sz - math.sin(sz)) / sz ** 3
    if z < -1e-8:
        sz = math.sqrt(-z)
        return (math.sinh(sz) - sz) / sz ** 3
    return 1 / 6


def propagate_two_body(r0: tuple[float, float, float], v0: tuple[float, float, float],
                        dt_seconds: float, mu: float = MU_EARTH,
                        max_iter: int = 100, tol: float = 1e-8) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Propagate (r0, v0) forward by dt_seconds using the universal
    Kepler equation solved by Newton's method. Returns (r, v) in the same
    units as the input (km, km/s)."""
    r0v = list(r0)
    v0v = list(v0)
    r0_norm = math.sqrt(sum(c * c for c in r0v))
    v0_norm = math.sqrt(sum(c * c for c in v0v))
    vr0 = sum(r0v[i] * v0v[i] for i in range(3)) / r0_norm

    alpha = 2 / r0_norm - v0_norm ** 2 / mu  # 1/a

    # initial guess for universal anomaly chi
    chi = math.sqrt(mu) * abs(alpha) * dt_seconds if abs(alpha) > 1e-10 else \
        math.sqrt(mu) * dt_seconds / r0_norm

    for _ in range(max_iter):
        z = alpha * chi ** 2
        C = _stumpff_c(z)
        S = _stumpff_s(z)
        r_dot_v_term = (r0_norm * vr0 / math.sqrt(mu)) * chi ** 2 * C
        F = (r_dot_v_term + (1 - alpha * r0_norm) * chi ** 3 * S
             + r0_norm * chi - math.sqrt(mu) * dt_seconds)
        dFdchi = (r0_norm * vr0 / math.sqrt(mu)) * chi * (1 - alpha * chi ** 2 * S) \
            + (1 - alpha * r0_norm) * chi ** 2 * C + r0_norm
        if abs(dFdchi) < 1e-14:
            break
        ratio = F / dFdchi
        chi -= ratio
        if abs(ratio) < tol:
            break

    z = alpha * chi ** 2
    C = _stumpff_c(z)
    S = _stumpff_s(z)

    f = 1 - (chi ** 2 / r0_norm) * C
    g = dt_seconds - (chi ** 3 / math.sqrt(mu)) * S

    r_new = [f * r0v[i] + g * v0v[i] for i in range(3)]
    r_new_norm = math.sqrt(sum(c * c for c in r_new))

    fdot = (math.sqrt(mu) / (r_new_norm * r0_norm)) * (alpha * chi ** 3 * S - chi)
    gdot = 1 - (chi ** 2 / r_new_norm) * C

    v_new = [fdot * r0v[i] + gdot * v0v[i] for i in range(3)]

    return tuple(r_new), tuple(v_new)
