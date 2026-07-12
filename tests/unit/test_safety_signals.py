from datetime import datetime, timezone
from uuid import UUID

from civicpulse.config import load_priority_policy
from civicpulse.domain import Category, Complaint
from civicpulse.priority import detect_safety_signals


POLICY = load_priority_policy("config/priority_policy.json")
NOW = datetime(2026, 7, 12, 8, tzinfo=timezone.utc)


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


def test_safety_signals_detect_multilingual_terms_and_deduplicate():
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


def test_negated_accident_does_not_trigger_signal():
    signals = detect_safety_signals(
        [complaint("00000000-0000-0000-0000-000000000003", "Tiada kemalangan and no accident")],
        POLICY,
    )

    assert all(signal.name != "accident_injury" for signal in signals)


def test_exposed_wire_is_critical_signal():
    signals = detect_safety_signals(
        [complaint("00000000-0000-0000-0000-000000000004", "Exposed wire near the road")],
        POLICY,
    )

    assert [signal.name for signal in signals] == ["exposed_electrical_hazard"]
