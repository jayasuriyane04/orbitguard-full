"""
Centralized, environment-driven configuration.

Nothing here is hardcoded. Every value has a safe local-dev default so the
service is runnable out of the box, but production deployments override
these via environment variables (or a .env file loaded by the platform).
"""
from __future__ import annotations

import os
from functools import lru_cache


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # --- App ---
    app_name: str = "ORBITGUARD"
    app_version: str = "0.2.0"
    environment: str = os.environ.get("ORBITGUARD_ENV", "development")

    # --- Database ---
    # SQLite fallback for local dev; set ORBITGUARD_DATABASE_URL for Postgres
    # in production, e.g. postgresql+psycopg2://user:pass@host:5432/orbitguard
    database_url: str = os.environ.get(
        "ORBITGUARD_DATABASE_URL", "sqlite:///./orbitguard.db"
    )

    # --- CORS ---
    cors_origins: list[str] = [
        o.strip()
        for o in os.environ.get(
            "ORBITGUARD_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if o.strip()
    ]

    # --- Data ingestion ---
    celestrak_base_url: str = os.environ.get(
        "ORBITGUARD_CELESTRAK_URL", "https://celestrak.org/NORAD/elements/gp.php"
    )
    ingestion_timeout_seconds: float = float(
        os.environ.get("ORBITGUARD_INGESTION_TIMEOUT", "20")
    )
    use_synthetic_fallback: bool = _bool_env("ORBITGUARD_USE_SYNTHETIC_FALLBACK", True)

    # --- Conjunction screening ---
    default_window_hours: float = float(os.environ.get("ORBITGUARD_WINDOW_HOURS", "24"))
    default_step_seconds: float = float(os.environ.get("ORBITGUARD_STEP_SECONDS", "30"))
    default_miss_distance_km: float = float(
        os.environ.get("ORBITGUARD_MISS_DISTANCE_KM", "25")
    )
    broad_phase_altitude_margin_km: float = float(
        os.environ.get("ORBITGUARD_ALTITUDE_MARGIN_KM", "150")
    )

    # --- Alerting ---
    alert_miss_distance_threshold_km: float = float(
        os.environ.get("ORBITGUARD_ALERT_MISS_DISTANCE_KM", "5")
    )

    # --- Background jobs ---
    enable_background_jobs: bool = _bool_env("ORBITGUARD_ENABLE_JOBS", False)
    ingestion_refresh_minutes: int = int(
        os.environ.get("ORBITGUARD_INGESTION_REFRESH_MINUTES", "180")
    )
    screening_refresh_minutes: int = int(
        os.environ.get("ORBITGUARD_SCREENING_REFRESH_MINUTES", "15")
    )

    # --- Trajectory cache ---
    trajectory_cache_max_entries: int = int(
        os.environ.get("ORBITGUARD_TRAJECTORY_CACHE_SIZE", "512")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
