"""
Debris removal prioritization.

Ranks non-maneuverable objects (debris and rocket bodies -- nothing that
can dodge on its own) by how much of an ongoing collision-risk burden they
represent, using signals already produced by the conjunction/risk engine
plus basic orbital-population context. This never claims the platform can
physically remove anything; it only informs which objects would be the
highest-value removal-mission targets.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.db.models import ConjunctionEvent, TrackedObject
from app.schemas.enums import ObjectType

WEIGHT_CONJUNCTION_FREQUENCY = 0.40
WEIGHT_AVERAGE_SEVERITY = 0.30
WEIGHT_ALTITUDE_CONGESTION = 0.15
WEIGHT_SIZE = 0.15

_SEVERITY_SCORE = {"LOW": 0.2, "MODERATE": 0.5, "HIGH": 0.75, "CRITICAL": 1.0}


@dataclass
class RemovalPriorityResult:
    norad_id: int
    object_name: str
    removal_priority_score: float
    conjunction_count: int
    average_severity_score: float
    explanation: str


def compute_removal_priorities(
    objects: list[TrackedObject], events: list[ConjunctionEvent],
) -> list[RemovalPriorityResult]:
    non_maneuverable = [o for o in objects if not o.maneuverable]
    if not non_maneuverable:
        return []

    events_by_norad: dict[int, list[ConjunctionEvent]] = defaultdict(list)
    for e in events:
        events_by_norad[e.primary_object_norad_id].append(e)
        events_by_norad[e.secondary_object_norad_id].append(e)

    # Altitude congestion: how many other tracked objects sit within a
    # narrow band of this one -- a crude proxy for "how crowded is this
    # object's neighborhood".
    def approx_altitude_band(o: TrackedObject) -> int:
        import math
        mu = 398600.4418
        n_rad_s = o.mean_motion_rev_per_day * 2 * math.pi / 86400.0
        a_km = (mu / (n_rad_s ** 2)) ** (1 / 3)
        return int((a_km - 6378.137) // 50)

    band_counts: dict[int, int] = defaultdict(int)
    for o in objects:
        band_counts[approx_altitude_band(o)] += 1
    max_band_count = max(band_counts.values(), default=1)

    max_conjunctions = max((len(events_by_norad[o.norad_id]) for o in non_maneuverable), default=0) or 1
    max_rcs = max((o.rcs_m2 or 0.0 for o in non_maneuverable), default=0.0) or 1.0

    results: list[RemovalPriorityResult] = []
    for o in non_maneuverable:
        related = events_by_norad.get(o.norad_id, [])
        conj_count = len(related)
        avg_severity = (
            sum(_SEVERITY_SCORE.get(e.severity.value if hasattr(e.severity, "value") else e.severity, 0.3)
                for e in related) / conj_count
            if conj_count else 0.0
        )
        congestion = band_counts[approx_altitude_band(o)] / max_band_count
        size_factor = (o.rcs_m2 or 0.0) / max_rcs
        frequency_factor = conj_count / max_conjunctions

        score = 100 * (
            WEIGHT_CONJUNCTION_FREQUENCY * frequency_factor
            + WEIGHT_AVERAGE_SEVERITY * avg_severity
            + WEIGHT_ALTITUDE_CONGESTION * congestion
            + WEIGHT_SIZE * size_factor
        )
        score = round(max(0.0, min(100.0, score)), 2)

        type_label = "rocket body" if o.object_type == ObjectType.ROCKET_BODY else "debris fragment"
        explanation = (
            f"This {type_label} was involved in {conj_count} tracked conjunction(s) "
            f"(avg severity {avg_severity:.2f}/1.0), sits in an altitude band shared by "
            f"~{band_counts[approx_altitude_band(o)]} other tracked objects, and has a "
            f"relative radar cross-section of {(o.rcs_m2 or 0.0):.2f} m^2 -- all factored "
            f"into a removal-priority score of {score:.1f}/100."
        )

        results.append(RemovalPriorityResult(
            norad_id=o.norad_id,
            object_name=o.name,
            removal_priority_score=score,
            conjunction_count=conj_count,
            average_severity_score=round(avg_severity, 4),
            explanation=explanation,
        ))

    return sorted(results, key=lambda r: r.removal_priority_score, reverse=True)
