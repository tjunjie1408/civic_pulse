from datetime import datetime, timedelta, timezone

import pytest

from civicpulse.geo import haversine_metres, temporal_gap_seconds, within_time_window


def test_same_coordinate_has_zero_distance():
    assert haversine_metres(3.1390, 101.6869, 3.1390, 101.6869) == pytest.approx(0, abs=1e-9)


def test_known_coordinate_distance_is_in_metres():
    distance = haversine_metres(3.1390, 101.6869, 3.1400, 101.6869)

    assert distance == pytest.approx(111.2, rel=0.01)


def test_temporal_window_handles_timezone_offsets_and_exact_boundary():
    first = datetime(2026, 7, 12, 8, tzinfo=timezone.utc)
    second = first.astimezone(timezone(timedelta(hours=8))) + timedelta(days=7)

    assert temporal_gap_seconds(first, second) == pytest.approx(7 * 24 * 3600)
    assert within_time_window(first, second, 7) is True
    assert within_time_window(first, second + timedelta(seconds=1), 7) is False


def test_naive_datetime_and_invalid_window_are_rejected():
    aware = datetime(2026, 7, 12, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="timezone"):
        temporal_gap_seconds(datetime(2026, 7, 12), aware)
    with pytest.raises(ValueError, match="positive"):
        within_time_window(aware, aware, 0)
