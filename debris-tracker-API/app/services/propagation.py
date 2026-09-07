"""
SGP4 propagation service.

Builds directly on the Satrec initialization approach from the original
app/propagation.py (works for both real TLEs and synthetic elements), and
adds what a full pipeline needs on top of a single state lookup:

- trajectory generation over a duration (for trails / conjunction screening)
- batch propagation of many objects at one timestamp (for the map view)
- an in-process LRU-style cache keyed on (norad_id, rounded timestamp) so
  repeated requests (e.g. re-drawing the same trajectory, or screening
  re-touching the same time step for many pairs) don't recompute SGP4
- geodetic (lat/lon/altitude) conversion for map rendering
"""
from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sgp4.api import Satrec, WGS72, jday

from app.core.config import get_settings
from app.db.models import TrackedObject

DEG2RAD = math.pi / 180.0
RAD2DEG = 180.0 / math.pi
EARTH_RADIUS_KM = 6378.137
EARTH_FLATTENING = 1 / 298.257223563
EARTH_ROTATION_RATE_RAD_S = 7.2921150e-5  # sidereal rotation rate


@dataclass(frozen=True)
class StateVector:
    norad_id: int
    timestamp: datetime
    position_km: tuple[float, float, float]
    velocity_km_s: tuple[float, float, float]
    altitude_km: float
    latitude_deg: float
    longitude_deg: float


def build_satrec(obj: TrackedObject) -> Satrec:
    """Initialize a Satrec either from a real TLE pair (preferred, carries
    the provider's own bstar/drag fit) or from classical elements (used for
    the synthetic fallback catalog, which has no TLE strings)."""
    if obj.tle_line1 and obj.tle_line2:
        return Satrec.twoline2rv(obj.tle_line1, obj.tle_line2)

    sat = Satrec()
    jd, fr = jday(
        obj.epoch.year, obj.epoch.month, obj.epoch.day,
        obj.epoch.hour, obj.epoch.minute, obj.epoch.second + obj.epoch.microsecond / 1e6,
    )
    epoch_days = (jd - 2433281.5) + fr
    no_kozai = obj.mean_motion_rev_per_day * 2 * math.pi / 1440.0
    sat.sgp4init(
        WGS72, "i", obj.norad_id, epoch_days, obj.bstar, 0.0, 0.0,
        obj.eccentricity, obj.arg_perigee_deg * DEG2RAD, obj.inclination_deg * DEG2RAD,
        obj.mean_anomaly_deg * DEG2RAD, no_kozai, obj.raan_deg * DEG2RAD,
    )
    return sat


def _eci_to_geodetic(x: float, y: float, z: float, when_utc: datetime) -> tuple[float, float, float]:
    """Approximate ECI -> geodetic (lat, lon, alt) conversion.

    Uses a spherical-Earth approximation for latitude/altitude (adequate for
    dashboard visualization) and corrects longitude for Earth's rotation
    since a fixed epoch. This is intentionally simple -- a WGS84 ellipsoidal
    solution would refine latitude/altitude slightly further.
    """
    r = math.sqrt(x * x + y * y + z * z)
    lat = math.asin(z / r) * RAD2DEG

    # Greenwich Mean Sidereal Time (rough) to rotate ECI -> ECEF longitude
    jd, fr = jday(when_utc.year, when_utc.month, when_utc.day,
                  when_utc.hour, when_utc.minute, when_utc.second + when_utc.microsecond / 1e6)
    t_ut1 = ((jd + fr) - 2451545.0) / 36525.0
    gmst_deg = (280.46061837 + 360.98564736629 * ((jd + fr) - 2451545.0)
                + 0.000387933 * t_ut1 ** 2) % 360.0

    lon_eci = math.atan2(y, x) * RAD2DEG
    lon = (lon_eci - gmst_deg + 540.0) % 360.0 - 180.0
    altitude = r - EARTH_RADIUS_KM
    return lat, lon, altitude


class TrajectoryCache:
    """Small in-process LRU cache for propagated states.

    Keyed on (norad_id, timestamp rounded to the nearest second). This is a
    process-local cache -- fine for a single-instance demo/hackathon
    deployment; a multi-worker production deployment would back this with
    Redis instead.
    """

    def __init__(self, max_entries: int | None = None):
        settings = get_settings()
        self.max_entries = max_entries or settings.trajectory_cache_max_entries
        self._store: OrderedDict[tuple[int, str], StateVector] = OrderedDict()

    def get(self, norad_id: int, when: datetime) -> StateVector | None:
        key = (norad_id, when.isoformat())
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def put(self, norad_id: int, when: datetime, state: StateVector) -> None:
        key = (norad_id, when.isoformat())
        self._store[key] = state
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


class Propagator:
    """Holds initialized Satrec objects for a set of tracked objects."""

    def __init__(self, objects: list[TrackedObject], cache: TrajectoryCache | None = None):
        self._objects = {o.norad_id: o for o in objects}
        self._satrecs = {o.norad_id: build_satrec(o) for o in objects}
        self._cache = cache or TrajectoryCache()

    def object(self, norad_id: int) -> TrackedObject:
        return self._objects[norad_id]

    def norad_ids(self) -> list[int]:
        return list(self._objects.keys())

    def state_at(self, norad_id: int, when: datetime) -> StateVector:
        if norad_id not in self._satrecs:
            raise KeyError(f"unknown norad_id {norad_id}")

        when_utc = when.astimezone(timezone.utc) if when.tzinfo else when.replace(tzinfo=timezone.utc)
        when_utc = when_utc.replace(microsecond=(when_utc.microsecond // 1000) * 1000)

        cached = self._cache.get(norad_id, when_utc)
        if cached is not None:
            return cached

        sat = self._satrecs[norad_id]
        jd, fr = jday(when_utc.year, when_utc.month, when_utc.day,
                      when_utc.hour, when_utc.minute,
                      when_utc.second + when_utc.microsecond / 1e6)
        error_code, r, v = sat.sgp4(jd, fr)
        if error_code != 0:
            raise ValueError(f"SGP4 propagation error code {error_code} for norad_id {norad_id}")

        lat, lon, alt = _eci_to_geodetic(r[0], r[1], r[2], when_utc)
        state = StateVector(
            norad_id=norad_id,
            timestamp=when_utc,
            position_km=tuple(r),
            velocity_km_s=tuple(v),
            altitude_km=alt,
            latitude_deg=lat,
            longitude_deg=lon,
        )
        self._cache.put(norad_id, when_utc, state)
        return state

    def trajectory(self, norad_id: int, start: datetime, duration: timedelta,
                    step: timedelta) -> list[StateVector]:
        n_steps = max(1, int(duration / step))
        return [self.state_at(norad_id, start + i * step) for i in range(n_steps + 1)]

    def batch_state_at(self, norad_ids: list[int], when: datetime) -> dict[int, StateVector]:
        out: dict[int, StateVector] = {}
        for nid in norad_ids:
            try:
                out[nid] = self.state_at(nid, when)
            except (KeyError, ValueError):
                continue
        return out
