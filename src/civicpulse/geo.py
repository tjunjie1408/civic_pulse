"""Pure geographic and timezone-aware temporal calculations."""

from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, isfinite, radians, sin, sqrt


EARTH_RADIUS_METRES = 6_371_008.8


def _validate_coordinate(latitude: float, longitude: float) -> None:
    if not isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("latitude must be finite and between -90 and 90")
    if not isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("longitude must be finite and between -180 and 180")


def haversine_metres(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Return the great-circle distance between two valid coordinates."""
    _validate_coordinate(latitude_a, longitude_a)
    _validate_coordinate(latitude_b, longitude_b)
    lat_a, lat_b = radians(latitude_a), radians(latitude_b)
    delta_lat = radians(latitude_b - latitude_a)
    delta_lon = radians(longitude_b - longitude_a)
    haversine = sin(delta_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_METRES * asin(sqrt(haversine))


def temporal_gap_seconds(first: datetime, second: datetime) -> float:
    """Return absolute UTC-normalized time difference in seconds."""
    if first.tzinfo is None or first.utcoffset() is None:
        raise ValueError("first datetime must include a timezone")
    if second.tzinfo is None or second.utcoffset() is None:
        raise ValueError("second datetime must include a timezone")
    return abs(
        first.astimezone(timezone.utc).timestamp()
        - second.astimezone(timezone.utc).timestamp()
    )


def within_time_window(first: datetime, second: datetime, max_days: float) -> bool:
    if not isfinite(max_days) or max_days <= 0:
        raise ValueError("max_days must be positive and finite")
    return temporal_gap_seconds(first, second) <= max_days * 24 * 60 * 60
