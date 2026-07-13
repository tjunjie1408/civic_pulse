from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from civicpulse.api import create_app
from civicpulse.domain import (
    Category,
    ClusteringStatus,
    Complaint,
    MatchState,
    ReviewStatus,
)
from civicpulse.service import ReviewAlreadyResolved, ReviewNotFound, ReviewStale


NOW = datetime(2026, 7, 13, 1, tzinfo=UTC)
LEFT_ID = UUID("00000000-0000-0000-0000-000000000011")
RIGHT_ID = UUID("00000000-0000-0000-0000-000000000012")
REVIEW_ID = UUID("20000000-0000-0000-0000-000000000001")
INCIDENT_ID = UUID("30000000-0000-0000-0000-000000000001")


def complaint(complaint_id: UUID, text: str) -> Complaint:
    return Complaint(
        id=complaint_id,
        text=text,
        normalized_text=text.lower(),
        category=Category.POTHOLE,
        latitude=3.12,
        longitude=101.68,
        reported_at=NOW,
    )


def evidence() -> SimpleNamespace:
    return SimpleNamespace(
        semantic_similarity=0.82,
        distance_metres=14.5,
        time_gap_seconds=3600.0,
        category_compatible=True,
        location_compatibility="compatible",
        first_location_entities=(),
        second_location_entities=(),
    )


def review(
    status: ReviewStatus = ReviewStatus.PENDING,
    *,
    created_at: datetime = NOW,
    resolved_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        review_id=REVIEW_ID,
        left_id=LEFT_ID,
        right_id=RIGHT_ID,
        matcher_recommendation=MatchState.REVIEW_REQUIRED,
        matcher_reasons=("semantic evidence is ambiguous",),
        matcher_evidence=evidence(),
        status=status,
        created_at=created_at,
        resolved_at=resolved_at,
        reviewed_by="demo-officer" if resolved_at else None,
        review_note="Same physical incident confirmed." if resolved_at else None,
        final_relationship_state=MatchState.AUTO_MATCH if resolved_at else None,
        decision_source="officer_review" if resolved_at else None,
        graph_version_at_creation="graph-v1",
        version=2 if resolved_at else 1,
    )


def incident(status: ClusteringStatus = ClusteringStatus.CONFLICT) -> SimpleNamespace:
    return SimpleNamespace(
        incident_id=INCIDENT_ID,
        complaint_ids=(LEFT_ID, RIGHT_ID),
        report_count=2,
        confirmed_edges=(),
        review_candidate_ids=(),
        review_candidates=(),
        centroid_latitude=3.12,
        centroid_longitude=101.68,
        radius_metres=14.5,
        earliest_reported_at=NOW,
        latest_reported_at=NOW,
        category_summary=(Category.POTHOLE,),
        status=status,
        conflict_reasons=("location contradiction",) if status is ClusteringStatus.CONFLICT else (),
    )


class FakeReviewService:
    def __init__(self) -> None:
        self.views = [
            SimpleNamespace(
                review=review(created_at=NOW + timedelta(hours=2)),
                complaint_a=complaint(LEFT_ID, "Pothole at Block A"),
                complaint_b=complaint(RIGHT_ID, "Road hole near Block A"),
            ),
            SimpleNamespace(
                review=review(
                    ReviewStatus.APPROVED,
                    created_at=NOW,
                    resolved_at=NOW + timedelta(hours=3),
                ),
                complaint_a=complaint(LEFT_ID, "Pothole at Block A"),
                complaint_b=complaint(RIGHT_ID, "Road hole near Block A"),
            ),
        ]
        self.resolution_args: list[tuple[UUID, bool, str, str | None]] = []

    def list_reviews(self, status: ReviewStatus | None = None):
        if status is None:
            return self.views
        return [item for item in self.views if item.review.status is status]

    def get_review(self, review_id: UUID):
        return next((item for item in self.views if item.review.review_id == review_id), None)

    def resolve_review(self, review_id: UUID, *, approve: bool, reviewer_id: str, note: str | None = None):
        self.resolution_args.append((review_id, approve, reviewer_id, note))
        if review_id == UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"):
            raise ReviewNotFound("unknown review")
        if reviewer_id == "stale":
            raise ReviewStale("review graph is stale")
        if reviewer_id == "resolved":
            raise ReviewAlreadyResolved("review is not pending")
        resolved = review(ReviewStatus.APPROVED if approve else ReviewStatus.REJECTED, resolved_at=NOW)
        self.views[0] = SimpleNamespace(
            review=resolved,
            complaint_a=complaint(LEFT_ID, "Pothole at Block A"),
            complaint_b=complaint(RIGHT_ID, "Road hole near Block A"),
        )
        return SimpleNamespace(
            review=resolved,
            final_relationship_state=MatchState.AUTO_MATCH if approve else MatchState.NO_MATCH,
            affected_complaint_ids=(LEFT_ID, RIGHT_ID),
            previous_incident_ids=(UUID("40000000-0000-0000-0000-000000000001"),),
            new_incident_ids=(INCIDENT_ID,),
            affected_incidents=(incident(),),
            resulting_priorities=(SimpleNamespace(level="high", reasons=("two reports",), policy_version="priority-v1"),),
            conflict_status=ClusteringStatus.CONFLICT,
        )


def client(service: FakeReviewService | None = None) -> TestClient:
    return TestClient(create_app(service=service or FakeReviewService()))


def test_review_list_filters_paginates_and_sorts_pending_then_resolved() -> None:
    response = client().get("/api/v1/reviews", params={"limit": 1, "offset": 0})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["items"][0]["status"] == "pending"


def test_review_list_status_filter_and_resolved_order_are_deterministic() -> None:
    response = client().get("/api/v1/reviews?status=approved")

    assert response.status_code == 200
    assert [item["status"] for item in response.json()["items"]] == ["approved"]


def test_review_detail_preserves_original_matcher_evidence_and_context() -> None:
    response = client().get(f"/api/v1/reviews/{REVIEW_ID}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["complaint_a"]["complaint_id"] == str(LEFT_ID)
    assert payload["complaint_b"]["complaint_id"] == str(RIGHT_ID)
    assert payload["original_matcher_recommendation"] == "review_required"
    assert payload["matcher_evidence"]["semantic_similarity"] == 0.82
    assert payload["matcher_evidence"]["geo_distance_metres"] == 14.5
    assert payload["matcher_evidence"]["time_difference_seconds"] == 3600.0
    assert payload["previous_incident_snapshot_ids"] == []
    assert payload["new_incident_snapshot_ids"] == []


def test_unknown_review_returns_stable_404() -> None:
    response = client().get("/api/v1/reviews/ffffffff-ffff-ffff-ffff-ffffffffffff")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "review_not_found"


def test_resolution_request_is_strict_and_approve_returns_mutation_result() -> None:
    service = FakeReviewService()
    response = client(service).post(
        f"/api/v1/reviews/{REVIEW_ID}/approve",
        json={"reviewer_id": "demo-officer", "note": "Same physical incident confirmed."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review"]["status"] == "approved"
    assert payload["final_relationship_state"] == "auto_match"
    assert payload["affected_complaint_ids"] == [str(LEFT_ID), str(RIGHT_ID)]
    assert payload["previous_incident_snapshot_ids"]
    assert payload["new_incident_snapshot_ids"] == [str(INCIDENT_ID)]
    assert payload["conflict_status"] == "conflict"
    assert payload["affected_incidents"][0]["priority"] is None
    assert service.resolution_args[0][1:] == (True, "demo-officer", "Same physical incident confirmed.")


def test_resolution_reject_returns_no_match_and_resolved_conflict_is_stable() -> None:
    service = FakeReviewService()
    rejected = client(service).post(
        f"/api/v1/reviews/{REVIEW_ID}/reject",
        json={"reviewer_id": "demo-officer"},
    )
    resolved = client(service).post(
        f"/api/v1/reviews/{REVIEW_ID}/approve",
        json={"reviewer_id": "resolved"},
    )

    assert rejected.status_code == 200
    assert rejected.json()["final_relationship_state"] == "no_match"
    assert resolved.status_code == 409
    assert resolved.json()["error"]["code"] == "review_already_resolved"


def test_resolution_maps_not_found_stale_and_payload_validation() -> None:
    missing = client().post(
        "/api/v1/reviews/ffffffff-ffff-ffff-ffff-ffffffffffff/approve",
        json={"reviewer_id": "demo-officer"},
    )
    stale = client().post(
        f"/api/v1/reviews/{REVIEW_ID}/approve",
        json={"reviewer_id": "stale"},
    )
    invalid = client().post(
        f"/api/v1/reviews/{REVIEW_ID}/approve",
        json={"reviewer_id": ""},
    )

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "review_not_found"
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "review_stale"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_review_openapi_is_deterministic() -> None:
    first = create_app().openapi()
    second = create_app().openapi()

    assert first == second
    assert "/api/v1/reviews" in first["paths"]
    assert "/api/v1/reviews/{review_id}/approve" in first["paths"]
    assert "/api/v1/reviews/{review_id}/reject" in first["paths"]
