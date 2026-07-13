"""Contract tests for Task 8.2 incident detail and review reads."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import httpx

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_models import (
    ComplaintResponse,
    IncidentDetailResponse,
    ReviewDetailResponse,
    ReviewEvidenceResponse,
    ReviewListResponse,
    ReviewSummaryResponse,
)
from civicpulse_dashboard.ui.incident_detail import incident_detail_rows
from civicpulse_dashboard.ui.review_queue import review_rows

ROOT = Path(__file__).parents[2]
OPENAPI = ROOT / "tests" / "contracts" / "openapi-v1.json"


def _complaint(complaint_id: str, text: str) -> dict[str, object]:
    return {
        "complaint_id": complaint_id,
        "text": text,
        "category": "pothole",
        "latitude": 1.3,
        "longitude": 103.8,
        "reported_at": "2026-07-13T00:00:00Z",
        "photo_path": None,
    }


def _summary(review_id: str, status: str = "pending") -> dict[str, object]:
    return {
        "review_id": review_id,
        "left_complaint_id": "00000000-0000-0000-0000-000000000001",
        "right_complaint_id": "00000000-0000-0000-0000-000000000002",
        "original_matcher_recommendation": "review_required",
        "matcher_reasons": ["nearby reports"],
        "status": status,
        "created_at": "2026-07-13T00:00:00Z",
        "resolved_at": None if status == "pending" else "2026-07-13T02:00:00Z",
        "reviewer_id": None if status == "pending" else "demo-officer",
        "review_note": None if status == "pending" else "Reviewed",
        "final_relationship_state": None if status == "pending" else "auto_match",
        "decision_source": None if status == "pending" else "officer_review",
        "graph_version": "graph-v1",
    }


def _detail(review_id: str) -> dict[str, object]:
    return {
        "review_id": review_id,
        "status": "pending",
        "complaint_a": _complaint(
            "00000000-0000-0000-0000-000000000001", "Pothole by the market"
        ),
        "complaint_b": _complaint(
            "00000000-0000-0000-0000-000000000002", "Road surface damaged near market"
        ),
        "original_matcher_recommendation": "review_required",
        "matcher_reasons": ["nearby reports"],
        "matcher_evidence": {
            "semantic_similarity": 0.94,
            "geo_distance_metres": 120.0,
            "time_difference_seconds": 10800.0,
            "category_compatibility": True,
            "location_compatibility": "compatible",
            "first_location_entities": [
                {"kind": "landmark", "value": "market", "raw": "the market"}
            ],
            "second_location_entities": [],
        },
        "created_at": "2026-07-13T00:00:00Z",
        "resolved_at": None,
        "reviewer_id": None,
        "review_note": None,
        "final_relationship_state": None,
        "decision_source": None,
        "graph_version": "graph-v1",
        "previous_incident_snapshot_ids": [],
        "new_incident_snapshot_ids": [],
    }


def _incident_detail() -> dict[str, object]:
    return {
        "incident_id": "00000000-0000-0000-0000-000000000010",
        "status": "confirmed",
        "category_summary": ["pothole"],
        "priority": {"level": "high", "reasons": ["reports"], "policy_version": "v1"},
        "confirmed_report_count": 2,
        "pending_candidate_count": 1,
        "centroid": {"latitude": 1.3, "longitude": 103.8},
        "radius_metres": 12.5,
        "earliest_reported_at": "2026-07-13T00:00:00Z",
        "latest_reported_at": "2026-07-13T01:00:00Z",
        "conflict_reasons": [],
        "complaint_ids": ["00000000-0000-0000-0000-000000000001"],
        "review_candidate_ids": ["00000000-0000-0000-0000-000000000002"],
        "confirmed_edges": [],
        "review_candidates": [],
    }


def test_review_and_incident_models_match_frozen_read_contract() -> None:
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    schemas = document["components"]["schemas"]

    for model, schema_name in (
        (ComplaintResponse, "ComplaintResponse"),
        (ReviewEvidenceResponse, "ReviewEvidenceResponse"),
        (ReviewSummaryResponse, "ReviewSummaryResponse"),
        (ReviewListResponse, "ReviewListResponse"),
        (ReviewDetailResponse, "ReviewDetailResponse"),
        (IncidentDetailResponse, "IncidentDetailResponse"),
    ):
        schema = schemas[schema_name]
        generated = model.model_json_schema()
        assert set(model.model_fields) == set(schema["properties"])
        assert generated["required"] == schema["required"]
        assert model.model_config["extra"] == "forbid"


def test_gateway_preserves_review_order_and_sends_status_pagination() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "items": [_summary("00000000-0000-0000-0000-000000000001")],
                "limit": 1,
                "offset": 3,
                "total": 5,
            },
        )

    with ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client:
        page = client.list_reviews(status="pending", limit=1, offset=3)

    assert [item.review_id for item in page.items] == [
        UUID("00000000-0000-0000-0000-000000000001")
    ]
    assert requests[0].url.path == "/api/v1/reviews"
    assert dict(requests[0].url.params) == {
        "status": "pending",
        "limit": "1",
        "offset": "3",
    }


def test_gateway_reads_review_detail_and_incident_detail_without_reinterpretation() -> None:
    review_id = "00000000-0000-0000-0000-000000000003"
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith(f"/reviews/{review_id}"):
            return httpx.Response(200, json=_detail(review_id))
        return httpx.Response(200, json=_incident_detail())

    with ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client:
        review = client.get_review(review_id)
        incident = client.get_incident("00000000-0000-0000-0000-000000000010")

    assert review.matcher_evidence is not None
    assert review.matcher_evidence.semantic_similarity == 0.94
    assert review.previous_incident_snapshot_ids == []
    assert incident.priority is not None
    assert incident.priority.level == "high"
    assert paths == [
        f"/api/v1/reviews/{review_id}",
        "/api/v1/incidents/00000000-0000-0000-0000-000000000010",
    ]


def test_review_rows_preserve_api_order_and_status_semantics() -> None:
    page = ReviewListResponse.model_validate(
        {
            "items": [
                _summary("00000000-0000-0000-0000-000000000001", "pending"),
                _summary("00000000-0000-0000-0000-000000000002", "approved"),
            ],
            "limit": 50,
            "offset": 0,
            "total": 2,
        }
    )

    rows = review_rows(page)

    assert [row["review_id"] for row in rows] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]
    assert rows[0]["status"] == "pending"
    assert rows[1]["status"] == "approved"


def test_incident_detail_rows_keep_confirmed_and_pending_counts_separate() -> None:
    detail = IncidentDetailResponse.model_validate(_incident_detail())

    rows = incident_detail_rows(detail)

    assert rows["confirmed_reports"] == 2
    assert rows["pending_candidates"] == 1
    assert rows["priority"] == "high"
    assert rows["snapshot_id"] == "00000000-0000-0000-0000-000000000010"
