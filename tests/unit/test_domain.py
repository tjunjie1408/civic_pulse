from datetime import datetime, timedelta, timezone
from math import nan
from uuid import UUID

import pytest
from pydantic import ValidationError

from civicpulse.domain import (
    Category,
    Complaint,
    ComplaintInput,
    LocationCompatibility,
    MatchDecision,
    MatchState,
    Incident,
    ClusteringStatus,
    RelationshipEdge,
)


def test_valid_multilingual_complaint_input_is_typed():
    complaint = ComplaintInput(
        text="Longkang dekat sekolah blocked lagi",
        latitude=3.1390,
        longitude=101.6869,
        reported_at=datetime.now(timezone.utc),
    )

    assert complaint.text == "Longkang dekat sekolah blocked lagi"
    assert complaint.category is None
    assert complaint.latitude == 3.1390


@pytest.mark.parametrize(
    "field, value",
    [
        ("text", "  "),
        ("text", "x" * 2001),
        ("latitude", nan),
        ("latitude", 91),
        ("longitude", -181),
        ("reported_at", datetime.now()),
        ("reported_at", datetime.now(timezone.utc) + timedelta(minutes=6)),
    ],
)
def test_invalid_complaint_input_is_rejected(field, value):
    payload = {
        "text": "A valid complaint description",
        "latitude": 3.1390,
        "longitude": 101.6869,
        "reported_at": datetime.now(timezone.utc),
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        ComplaintInput.model_validate(payload)


def test_complaint_has_stable_identity_and_other_category_default():
    complaint = Complaint(
        text="Something is wrong near the market",
        latitude=3.1390,
        longitude=101.6869,
        reported_at=datetime.now(timezone.utc),
        normalized_text="something is wrong near the market",
    )

    assert isinstance(complaint.id, UUID)
    assert complaint.category is Category.OTHER


def test_match_decision_rejects_invalid_similarity_and_distance():
    with pytest.raises(ValidationError):
        MatchDecision(
            decision=MatchState.REVIEW_REQUIRED,
            auto_match=False,
            review_required=True,
            category_compatible=False,
            location_compatibility=LocationCompatibility.UNKNOWN,
            first_location_entities=(),
            second_location_entities=(),
            distance_metres=-1,
            time_gap_seconds=0,
            semantic_similarity=1.1,
            reasons=("category mismatch",),
        )


def test_incident_candidate_ids_must_match_candidate_edges():
    with pytest.raises(ValidationError, match="review_candidate_ids"):
        Incident(
            incident_id=UUID("10000000-0000-0000-0000-000000000001"),
            complaint_ids=(UUID("00000000-0000-0000-0000-000000000001"),),
            report_count=1,
            confirmed_edges=(),
            review_candidate_ids=(),
            review_candidates=(
                RelationshipEdge(
                    left_id=UUID("00000000-0000-0000-0000-000000000001"),
                    right_id=UUID("00000000-0000-0000-0000-000000000002"),
                    decision=MatchState.REVIEW_REQUIRED,
                    reasons=("ambiguous",),
                ),
            ),
            centroid_latitude=3.139,
            centroid_longitude=101.687,
            radius_metres=0,
            earliest_reported_at=datetime.now(timezone.utc),
            latest_reported_at=datetime.now(timezone.utc),
            category_summary=(Category.POTHOLE,),
            status=ClusteringStatus.ISOLATED,
        )
