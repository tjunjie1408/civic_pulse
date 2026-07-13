"""Contract tests for Task 8.4 review resolution gateway behavior."""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import (
    ReviewMutationResponse,
    ReviewResolutionRequest,
    SeedResetResponse,
)


REVIEW_ID = "00000000-0000-0000-0000-000000000003"


def _complaint(complaint_id: str, text: str) -> dict[str, object]:
    return {
        "complaint_id": complaint_id,
        "text": text,
        "category": "pothole",
        "latitude": 3.07,
        "longitude": 101.52,
        "reported_at": "2026-07-13T00:00:00Z",
        "photo_path": None,
    }


def _incident(incident_id: str, *, conflict: bool = False) -> dict[str, object]:
    return {
        "incident_id": incident_id,
        "status": "conflict" if conflict else "confirmed",
        "category_summary": ["pothole"],
        "priority": None
        if conflict
        else {"level": "high", "reasons": ["reports"], "policy_version": "v1"},
        "confirmed_report_count": 2,
        "pending_candidate_count": 0,
        "centroid": {"latitude": 3.07, "longitude": 101.52},
        "radius_metres": 20.0,
        "earliest_reported_at": "2026-07-13T00:00:00Z",
        "latest_reported_at": "2026-07-13T01:00:00Z",
        "conflict_reasons": ["contradictory evidence"] if conflict else [],
    }


def _mutation_payload(*, conflict: bool = False) -> dict[str, object]:
    return {
        "review": {
            "review_id": REVIEW_ID,
            "status": "approved",
            "complaint_a": _complaint(
                "00000000-0000-0000-0000-000000000001", "Pothole by the market"
            ),
            "complaint_b": _complaint(
                "00000000-0000-0000-0000-000000000002", "Road surface damaged near market"
            ),
            "original_matcher_recommendation": "review_required",
            "matcher_reasons": ["nearby reports"],
            "matcher_evidence": None,
            "created_at": "2026-07-13T00:00:00Z",
            "resolved_at": "2026-07-13T02:00:00Z",
            "reviewer_id": "demo-officer",
            "review_note": "Same physical incident.",
            "final_relationship_state": "auto_match",
            "decision_source": "officer_review",
            "graph_version": "graph-v2",
            "previous_incident_snapshot_ids": [
                "00000000-0000-0000-0000-000000000010"
            ],
            "new_incident_snapshot_ids": ["00000000-0000-0000-0000-000000000011"],
        },
        "final_relationship_state": "auto_match",
        "affected_complaint_ids": [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ],
        "previous_incident_snapshot_ids": [
            "00000000-0000-0000-0000-000000000010"
        ],
        "new_incident_snapshot_ids": ["00000000-0000-0000-0000-000000000011"],
        "affected_incidents": [_incident("00000000-0000-0000-0000-000000000011", conflict=conflict)],
        "resulting_priorities": [None if conflict else {"level": "high", "reasons": ["reports"], "policy_version": "v1"}],
        "conflict_status": "conflict" if conflict else None,
    }


def test_review_resolution_request_is_strict_and_bounded() -> None:
    request = ReviewResolutionRequest(reviewer_id=" demo-officer ", note="Same physical incident.")

    assert request.reviewer_id == "demo-officer"
    with pytest.raises(ValueError):
        ReviewResolutionRequest(reviewer_id="   ")
    with pytest.raises(ValueError):
        ReviewResolutionRequest(reviewer_id="demo-officer", note="x" * 1001)


def test_gateway_posts_review_resolution_and_parses_transition() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_mutation_payload())

    with ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client:
        response = client.approve_review(REVIEW_ID, "demo-officer", "Same physical incident.")

    assert isinstance(response, ReviewMutationResponse)
    assert response.review.review_id == UUID(REVIEW_ID)
    assert response.new_incident_snapshot_ids == [
        UUID("00000000-0000-0000-0000-000000000011")
    ]
    assert requests[0].url.path == f"/api/v1/reviews/{REVIEW_ID}/approve"
    assert json.loads(requests[0].content) == {
        "reviewer_id": "demo-officer",
        "note": "Same physical incident.",
    }


def test_gateway_rejects_contract_mismatch_and_preserves_conflict_priority_null() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_mutation_payload(conflict=True))

    with ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client:
        response = client.reject_review(REVIEW_ID, "demo-officer", None)

    assert response.conflict_status == "conflict"
    assert response.resulting_priorities == [None]


def test_gateway_reset_posts_without_client_seed_path_and_parses_summary() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "seed_version": "shah-alam-demo-v1",
                "seed_checksum": "a" * 64,
                "complaint_count": 120,
                "incident_count": 60,
                "review_counts": {"pending": 4, "approved": 8, "rejected": 3},
                "priority_counts": {"low": 20, "medium": 25, "high": 12, "critical": 3},
            },
        )

    with ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client:
        response = client.reset_demo()

    assert isinstance(response, SeedResetResponse)
    assert response.complaint_count == 120
    assert requests[0].url.path == "/api/v1/admin/reset"
    assert requests[0].content == b""


def test_review_stale_is_exposed_as_a_safe_conflict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": "review_stale",
                    "message": "The review graph is stale and must be reloaded.",
                    "details": {},
                    "request_id": "request-1",
                }
            },
        )

    with (
        ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(DashboardApiError) as raised,
    ):
        client.approve_review(REVIEW_ID, "demo-officer", "Keep this note")

    assert raised.value.code == "review_stale"
    assert raised.value.status_code == 409
