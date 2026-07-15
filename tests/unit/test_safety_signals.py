from datetime import UTC, datetime
from uuid import UUID

import pytest

from civicpulse.config import load_priority_policy
from civicpulse.domain import Category, Complaint
from civicpulse.priority import detect_safety_signals

POLICY = load_priority_policy("config/priority_policy.json")
NOW = datetime(2026, 7, 12, 8, tzinfo=UTC)


def complaint(complaint_id: str, text: str) -> Complaint:
    return Complaint(
        id=UUID(complaint_id),
        text=text,
        normalized_text=text.casefold(),
        category=Category.FLOODING,
        latitude=3.1390,
        longitude=101.6869,
        reported_at=NOW,
    )


def test_safety_signals_detect_multilingual_terms_and_deduplicate() -> None:
    signals = detect_safety_signals(
        [
            complaint("00000000-0000-0000-0000-000000000001", "Banjir and flood jalan blocked"),
            complaint("00000000-0000-0000-0000-000000000002", "Air naik, flood again"),
        ],
        POLICY,
    )

    assert {signal.name for signal in signals} == {"active_flooding", "blocked_road"}
    flooding = next(signal for signal in signals if signal.name == "active_flooding")
    assert len(flooding.complaint_ids) == 2
    assert flooding.matched_terms


def test_negated_accident_does_not_trigger_signal() -> None:
    signals = detect_safety_signals(
        [complaint("00000000-0000-0000-0000-000000000003", "Tiada kemalangan and no accident")],
        POLICY,
    )

    assert all(signal.name != "accident_injury" for signal in signals)


def test_exposed_wire_is_critical_signal() -> None:
    signals = detect_safety_signals(
        [complaint("00000000-0000-0000-0000-000000000004", "Exposed wire near the road")],
        POLICY,
    )

    assert [signal.name for signal in signals] == ["exposed_electrical_hazard"]


@pytest.mark.parametrize(
    "text",
    [
        "Road under flood",
        "Road is flooding",
        "Road was flooded",
        "Road is flooding now",
        "Kawasan sudah flooded",
        "Banjir sedang berlaku",
        "Air naik dan jalan banjir",
    ],
)
def test_active_flooding_signal_recognizes_common_inflections(text: str) -> None:
    signals = detect_safety_signals(
        [complaint("00000000-0000-0000-0000-000000000005", text)],
        POLICY,
    )

    assert [signal.name for signal in signals] == ["active_flooding"]


def test_negated_flooding_does_not_trigger_signal() -> None:
    signals = detect_safety_signals(
        [complaint("00000000-0000-0000-0000-000000000006", "No flooding near the road")],
        POLICY,
    )

    assert all(signal.name != "active_flooding" for signal in signals)


def test_floodlight_does_not_trigger_flooding_signal() -> None:
    signals = detect_safety_signals(
        [complaint("00000000-0000-0000-0000-000000000007", "Floodlight is broken")],
        POLICY,
    )

    assert all(signal.name != "active_flooding" for signal in signals)


@pytest.mark.parametrize(
    "text",
    [
        "Flooding has subsided",
        "Was flooded last week but clear now",
        "Road is no longer flooded",
        "Not currently flooding",
        "Tak banjir",
        "Tidak banjir",
        "Banjir sudah surut",
        "Flooded with complaints",
        "Floodlight rosak",
    ],
)
def test_inactive_flooding_context_does_not_trigger_signal(text: str) -> None:
    signals = detect_safety_signals(
        [complaint("00000000-0000-0000-0000-000000000008", text)],
        POLICY,
    )

    assert all(signal.name != "active_flooding" for signal in signals)
