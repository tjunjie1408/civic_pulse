from datetime import datetime, timezone
from uuid import UUID

import pytest

from civicpulse.clustering import ClusteringRelationship, build_incidents
from civicpulse.domain import Category, Complaint, LocationCompatibility, MatchDecision, MatchState


NOW = datetime(2026, 7, 12, 8, tzinfo=timezone.utc)
A_ID = UUID("00000000-0000-0000-0000-000000000001")
B_ID = UUID("00000000-0000-0000-0000-000000000002")
C_ID = UUID("00000000-0000-0000-0000-000000000003")
D_ID = UUID("00000000-0000-0000-0000-000000000004")


def complaint(complaint_id: UUID, *, category: Category = Category.POTHOLE) -> Complaint:
    return Complaint(
        id=complaint_id,
        text=f"Pothole at Block {complaint_id.int}",
        normalized_text=f"pothole at block {complaint_id.int}",
        latitude=3.1390 + complaint_id.int * 0.000001,
        longitude=101.6869,
        reported_at=NOW,
        category=category,
    )


def decision(state: MatchState, *reasons: str) -> MatchDecision:
    return MatchDecision(
        decision=state,
        auto_match=state is MatchState.AUTO_MATCH,
        review_required=state is MatchState.REVIEW_REQUIRED,
        category_compatible=state is not MatchState.NO_MATCH,
        location_compatibility=LocationCompatibility.COMPATIBLE,
        first_location_entities=(),
        second_location_entities=(),
        distance_metres=10,
        time_gap_seconds=60,
        semantic_similarity=0.95,
        reasons=reasons or (state.value,),
    )


def edge(left: UUID, right: UUID, state: MatchState, *reasons: str) -> ClusteringRelationship:
    return ClusteringRelationship(left_id=left, right_id=right, decision=decision(state, *reasons))


def test_empty_input_returns_no_incidents():
    assert build_incidents([], []) == []


def test_isolated_complaint_forms_one_isolated_incident():
    incidents = build_incidents([complaint(A_ID)], [])

    assert len(incidents) == 1
    assert incidents[0].complaint_ids == (A_ID,)
    assert incidents[0].status.value == "isolated"
    assert incidents[0].report_count == 1


def test_two_auto_edges_form_confirmed_incident():
    incidents = build_incidents(
        [complaint(A_ID), complaint(B_ID)],
        [edge(A_ID, B_ID, MatchState.AUTO_MATCH, "same incident")],
    )

    assert len(incidents) == 1
    assert incidents[0].complaint_ids == (A_ID, B_ID)
    assert incidents[0].status.value == "confirmed"
    assert len(incidents[0].confirmed_edges) == 1
    assert incidents[0].category_summary == (Category.POTHOLE,)
    assert incidents[0].earliest_reported_at == NOW
    assert incidents[0].latest_reported_at == NOW
    assert incidents[0].centroid_latitude > 3.1390
    assert incidents[0].radius_metres > 0


def test_confirmed_edges_are_transitive_but_review_edge_does_not_bridge():
    incidents = build_incidents(
        [complaint(A_ID), complaint(B_ID), complaint(C_ID)],
        [
            edge(A_ID, B_ID, MatchState.AUTO_MATCH),
            edge(B_ID, C_ID, MatchState.REVIEW_REQUIRED, "ambiguous location"),
        ],
    )

    assert [incident.complaint_ids for incident in incidents] == [(A_ID, B_ID), (C_ID,)]
    assert incidents[0].review_candidate_ids == (C_ID,)
    assert incidents[1].review_candidate_ids == (B_ID,)


def test_auto_chain_forms_one_confirmed_component():
    incidents = build_incidents(
        [complaint(A_ID), complaint(B_ID), complaint(C_ID)],
        [edge(A_ID, B_ID, MatchState.AUTO_MATCH), edge(B_ID, C_ID, MatchState.AUTO_MATCH)],
    )

    assert len(incidents) == 1
    assert incidents[0].complaint_ids == (A_ID, B_ID, C_ID)
    assert len(incidents[0].confirmed_edges) == 2


def test_no_match_is_excluded_from_incidents_and_candidates():
    incidents = build_incidents(
        [complaint(A_ID), complaint(B_ID)],
        [edge(A_ID, B_ID, MatchState.NO_MATCH, "different blocks")],
    )

    assert [incident.complaint_ids for incident in incidents] == [(A_ID,), (B_ID,)]
    assert all(not incident.review_candidate_ids for incident in incidents)
    assert all(not incident.confirmed_edges for incident in incidents)


def test_conflicting_no_match_inside_auto_component_is_explicit_conflict():
    incidents = build_incidents(
        [complaint(A_ID), complaint(B_ID), complaint(C_ID)],
        [
            edge(A_ID, B_ID, MatchState.AUTO_MATCH),
            edge(B_ID, C_ID, MatchState.AUTO_MATCH),
            edge(A_ID, C_ID, MatchState.NO_MATCH, "explicit block conflict"),
        ],
    )

    assert len(incidents) == 1
    assert incidents[0].status.value == "conflict"
    assert incidents[0].conflict_reasons
    assert "explicit block conflict" in incidents[0].conflict_reasons[0]


def test_incident_ids_and_memberships_are_input_order_independent():
    relationships = [edge(A_ID, B_ID, MatchState.AUTO_MATCH)]
    forward = build_incidents([complaint(A_ID), complaint(B_ID), complaint(C_ID)], relationships)
    reverse = build_incidents([complaint(C_ID), complaint(B_ID), complaint(A_ID)], relationships)

    assert [(incident.incident_id, incident.complaint_ids) for incident in forward] == [
        (incident.incident_id, incident.complaint_ids) for incident in reverse
    ]


def test_duplicate_relationship_records_are_deduplicated():
    relationship = edge(A_ID, B_ID, MatchState.AUTO_MATCH, "same")
    incidents = build_incidents([complaint(A_ID), complaint(B_ID)], [relationship, relationship])

    assert len(incidents) == 1
    assert len(incidents[0].confirmed_edges) == 1


def test_duplicate_complaint_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate complaint"):
        build_incidents([complaint(A_ID), complaint(A_ID)], [])
