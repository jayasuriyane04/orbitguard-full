import type { TrackedObject } from "@/types/api";

const MU_EARTH = 398600.4418; // km^3/s^2
const EARTH_RADIUS_KM = 6378.137;

/** Approximate circular-orbit altitude (km) from mean motion (rev/day). */
export function approxAltitudeKm(obj: TrackedObject): number {
  const nRadS = (obj.elements.mean_motion_rev_per_day * 2 * Math.PI) / 86400;
  const aKm = Math.cbrt(MU_EARTH / (nRadS * nRadS));
  return aKm - EARTH_RADIUS_KM;
}
