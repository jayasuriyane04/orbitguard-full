from enum import Enum


class ObjectType(str, Enum):
    ACTIVE_SATELLITE = "ACTIVE_SATELLITE"
    DEBRIS = "DEBRIS"
    ROCKET_BODY = "ROCKET_BODY"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class ManeuverDirection(str, Enum):
    PROGRADE = "PROGRADE"
    RETROGRADE = "RETROGRADE"
    RADIAL_OUTWARD = "RADIAL_OUTWARD"
    RADIAL_INWARD = "RADIAL_INWARD"
    NORMAL = "NORMAL"
    ANTI_NORMAL = "ANTI_NORMAL"


class DataSource(str, Enum):
    CELESTRAK = "CELESTRAK"
    SYNTHETIC = "SYNTHETIC"
    MANUAL = "MANUAL"
