"""Contract and pure-projection tests for Task 8.3 dashboard workflows."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import (
    ComplaintCreateRequest,
    ComplaintSubmissionResponse,
    IncidentListResponse,
)
from civicpulse_dashboard.state import DashboardSessionState
from civicpulse_dashboard.ui.hotspot_map import hotspot_rows
from civicpulse_dashboard.ui.submit_complaint import draft_fingerprint


def _incident(
    incident_id: str,
    *,
    status: str = "confirmed",
    priority: str | None = "high",
) -> dict[str, object]:
    return {
        "incident_id": incident_id,
        "status": status,
        "category_summary": ["flooding"],
        "priority": (
            None
            if priority is None
            else {"level": priority, "reasons": ["test"], "policy_version": "v1"}
        ),
        "confirmed_report_count": 4,
        "pending_candidate_count": 2,
        "centroid": {"latitude": 3.07, "longitude": 101.52},
        "radius_metres": 45.0,
        "earliest_reported_at": "2026-07-13T00:00:00Z",
        "latest_reported_at": "2026-07-13T01:00:00Z",
        "conflict_reasons": ["contradictory evidence"] if status == "conflict" else [],
    }


def _submission_payload() -> dict[str, object]:
    return {
        "complaint": {
            "complaint_id": "00000000-0000-0000-0000-000000000010",
            "text": "Water pooling near the school access road",
            "category": "flooding",
            "latitude": 3.07,
            "longitude": 101.52,
            "reported_at": "2026-07-13T01:00:00Z",
            "photo_path": None,
        },
        "created": True,
        "replayed": False,
        "relationship_decisions": [],
        "incident_transition": {
            "previous_incident_snapshot_ids": [
                "00000000-0000-0000-0000-000000000001"
            ],
            "current_incident_snapshot_ids": ["00000000-0000-0000-0000-000000000002"],
        },
        "incidents": [_incident("00000000-0000-0000-0000-000000000002")],
        "priorities": [
            {"level": "high", "reasons": ["test"], "policy_version": "v1"}
        ],
    }


def test_gateway_posts_strict_complaint_payload_and_parses_transition() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json=_submission_payload())

    request = ComplaintCreateRequest(
        text="Water pooling near the school access road",
        latitude=3.07,
        longitude=101.52,
        reported_at="2026-07-13T09:00:00+08:00",
        category="flooding",
    )
    with ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client:
        response = client.submit_complaint(request, "stable-key")

    assert isinstance(response, ComplaintSubmissionResponse)
    assert response.created is True
    assert response.incident_transition.current_incident_snapshot_ids == [
        UUID("00000000-0000-0000-0000-000000000002")
    ]
    assert requests[0].url.path == "/api/v1/complaints"
    assert requests[0].headers["Idempotency-Key"] == "stable-key"
    assert requests[0].content.find(b'"photo_path"') >= 0


def test_gateway_exposes_idempotency_conflict_as_safe_domain_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": "idempotency_conflict",
                    "message": "The Idempotency-Key was reused with a different request.",
                    "details": {},
                    "request_id": "request-1",
                }
            },
        )

    request = ComplaintCreateRequest(
        text="New complaint text",
        latitude=3.07,
        longitude=101.52,
        reported_at="2026-07-13T09:00:00+08:00",
        category="flooding",
    )
    with (
        ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(DashboardApiError) as raised,
    ):
        client.submit_complaint(request, "reused-key")

    assert raised.value.code == "idempotency_conflict"
    assert raised.value.status_code == 409


def test_hotspot_rows_only_use_confirmed_incidents_and_keep_pending_separate() -> None:
    page = IncidentListResponse.model_validate(
        {
            "items": [
                _incident("00000000-0000-0000-0000-000000000001"),
                _incident(
                    "00000000-0000-0000-0000-000000000002",
                    status="conflict",
                    priority=None,
                ),
            ],
            "limit": 50,
            "offset": 0,
            "total": 2,
        }
    )

    rows = hotspot_rows(page)

    assert [row["incident_id"] for row in rows] == [
        "00000000-0000-0000-0000-000000000001"
    ]
    assert rows[0]["confirmed_reports"] == 4
    assert rows[0]["pending_candidates"] == 2
    assert rows[0]["priority"] == "high"


def test_submission_state_reuses_key_for_same_draft_and_rotates_on_change() -> None:
    state = DashboardSessionState()
    first = draft_fingerprint("Blocked drain", 3.07, 101.52, "blocked_drain")
    second = draft_fingerprint("Blocked drain", 3.071, 101.52, "blocked_drain")

    first_key = state.ensure_idempotency_key(first)
    assert state.ensure_idempotency_key(first) == first_key
    assert state.ensure_idempotency_key(second) != first_key


def test_snapshot_transition_selects_unique_current_successor() -> None:
    state = DashboardSessionState()
    state.selected_incident_snapshot_id = "old"

    state.apply_mutation_transition(previous_ids=["old"], current_ids=["new"])

    assert state.selected_incident_snapshot_id == "new"
    assert state.last_mutation_result == {
        "previous_incident_snapshot_ids": ["old"],
        "new_incident_snapshot_ids": ["new"],
    }
