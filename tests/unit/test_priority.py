from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from civicpulse.config import load_priority_policy
from civicpulse.domain import (
    Category,
    ClusteringStatus,
    Complaint,
    Incident,
    PriorityLevel,
    PriorityStatus,
    RelationshipEdge,
    SensitiveLocation,
)
from civicpulse.priority import assess_priority


POLICY = load_priority_policy("config/priority_policy.json")
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def complaint(complaint_id: int, *, text: str = "Pothole at Block A", photo: bool = False) -> Complaint:
    return Complaint(
        id=UUID(f"00000000-0000-0000-0000-{complaint_id:012d}"),
        text=text,
        normalized_text=text.casefold(),
        category=Category.POTHOLE,
        latitude=3.1390 + complaint_id * 0.00001,
        longitude=101.6869,
        reported_at=NOW - timedelta(hours=12),
        photo_path="photo.jpg" if photo else None,
    )


def incident(members: tuple[Complaint, ...], *, status: ClusteringStatus = ClusteringStatus.CONFIRMED, candidates: int = 0) -> Incident:
    ids = tuple(member.id for member in members)
    candidate_ids = tuple(UUID(f"00000000-0000-0000-0000-{9000 + index:012d}") for index in range(candidates))
    return Incident(
        incident_id=UUID("10000000-0000-0000-0000-000000000001"),
        complaint_ids=ids,
        report_count=len(ids),
        confirmed_edges=(),
        review_candidate_ids=candidate_ids,
        review_candidates=(),
        centroid_latitude=3.1390,
        centroid_longitude=101.6869,
        radius_metres=10,
        earliest_reported_at=min(member.reported_at for member in members),
        latest_reported_at=max(member.reported_at for member in members),
        category_summary=(Category.POTHOLE,),
        status=status,
        conflict_reasons=("contradictory graph",) if status is ClusteringStatus.CONFLICT else (),
    )


def test_isolated_single_report_is_low():
    result = assess_priority(incident((complaint(1),), status=ClusteringStatus.ISOLATED), [complaint(1)], [], POLICY, NOW)

    assert result.level is PriorityLevel.LOW
    assert result.status is PriorityStatus.SCORED
    assert result.confirmed_report_count == 1


def test_report_volume_thresholds_are_exact_and_configured():
    medium = assess_priority(incident(tuple(complaint(index) for index in range(1, 3))), [complaint(1), complaint(2)], [], POLICY, NOW)
    high = assess_priority(incident(tuple(complaint(index) for index in range(1, 11))), [complaint(index) for index in range(1, 11)], [], POLICY, NOW)

    assert medium.level is PriorityLevel.MEDIUM
    assert "multi_report_incident" in medium.triggered_rules
    assert high.level is PriorityLevel.HIGH
    assert "high_confirmed_report_volume" in high.triggered_rules


def test_unresolved_duration_escalates_at_configured_boundary():
    old = complaint(1)
    old = old.model_copy(update={"reported_at": NOW - timedelta(hours=POLICY.critical_unresolved_hours)})
    result = assess_priority(incident((old,)), [old], [], POLICY, NOW)

    assert result.level is PriorityLevel.CRITICAL
    assert "critical_persistence" in result.triggered_rules


def test_safety_signal_escalates_and_explains():
    item = complaint(1, text="Exposed wire near road")
    result = assess_priority(incident((item,)), [item], [], POLICY, NOW)

    assert result.level is PriorityLevel.CRITICAL
    assert "critical_safety_signal" in result.triggered_rules
    assert any("exposed_electrical_hazard" in reason for reason in result.reasons)


def test_sensitive_location_escalates_without_changing_confirmed_count():
    item = complaint(1)
    location = SensitiveLocation(id="school-1", kind="school", latitude=item.latitude, longitude=item.longitude)
    result = assess_priority(incident((item,)), [item], [location], POLICY, NOW)

    assert result.level is PriorityLevel.HIGH
    assert result.confirmed_report_count == 1
    assert "sensitive_location_exposure" in result.triggered_rules


def test_review_candidates_do_not_affect_priority():
    members = (complaint(1), complaint(2))
    with_candidates = assess_priority(incident(members, candidates=3), list(members), [], POLICY, NOW)
    without_candidates = assess_priority(incident(members), list(members), [], POLICY, NOW)

    assert with_candidates.level is without_candidates.level
    assert with_candidates.status is without_candidates.status
    assert with_candidates.points == without_candidates.points
    assert with_candidates.triggered_rules == without_candidates.triggered_rules
    assert with_candidates.confirmed_report_count == 2
    assert with_candidates.pending_candidate_count == 3


def test_conflict_incident_is_not_assigned_operational_priority():
    item = complaint(1, text="Pothole and exposed wire")
    result = assess_priority(
        incident((item,), status=ClusteringStatus.CONFLICT),
        [item],
        [],
        POLICY,
        NOW,
    )

    assert result.level is PriorityLevel.REVIEW_REQUIRED
    assert result.status is PriorityStatus.REVIEW_REQUIRED
    assert result.points == 0
    assert "clustering_conflict_requires_review" in result.triggered_rules


def test_assessment_is_deterministic():
    item = complaint(1, text="Flood near school", photo=True)
    location = SensitiveLocation(id="school-1", kind="school", latitude=item.latitude, longitude=item.longitude)

    first = assess_priority(incident((item,)), [item], [location], POLICY, NOW)
    second = assess_priority(incident((item,)), [item], [location], POLICY, NOW)

    assert first == second
