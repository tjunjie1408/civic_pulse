from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from fastapi.testclient import TestClient

from civicpulse.runtime import RuntimeSettings, build_runtime

pytestmark = pytest.mark.e2e

TEXT = "Longkang dekat sekolah blocked lagi, hujan terus air naik."
TARGET_ID = uuid5(
    NAMESPACE_URL,
    "civicpulse-seed:shah-alam-demo-v1:complaint-025",
)


def incident_containing(client: TestClient, complaint_id: UUID) -> dict[str, object]:
    page = client.get("/api/v1/incidents", params={"limit": 100, "offset": 0})
    assert page.status_code == 200
    for item in page.json()["items"]:
        detail = client.get(f"/api/v1/incidents/{item['incident_id']}")
        assert detail.status_code == 200
        if str(complaint_id) in detail.json()["complaint_ids"]:
            return detail.json()
    raise AssertionError(f"complaint {complaint_id} is missing from incident snapshots")


def pending_review_for_pair(
    client: TestClient,
    left_id: UUID,
    right_id: UUID,
) -> dict[str, object]:
    offset = 0
    while True:
        response = client.get(
            "/api/v1/reviews",
            params={"status": "pending", "limit": 100, "offset": offset},
        )
        assert response.status_code == 200
        payload = response.json()
        for item in payload["items"]:
            pair = {item["left_complaint_id"], item["right_complaint_id"]}
            if pair == {str(left_id), str(right_id)}:
                return item
        offset += len(payload["items"])
        if offset >= payload["total"]:
            raise AssertionError("expected review pair was not surfaced")


def test_seed_submit_review_approve_and_refresh_full_demo(tmp_path: Path) -> None:
    runtime = build_runtime(
        RuntimeSettings(
            database_path=tmp_path / "civicpulse.db",
            seed_path=Path("data/seed_complaints.json"),
            sensitive_locations_path=Path("data/sensitive_locations.json"),
        )
    )
    client = TestClient(runtime.app)

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["core_ready"] is True
    before_page = client.get("/api/v1/incidents", params={"status": "confirmed", "limit": 100})
    assert before_page.status_code == 200
    assert before_page.json()["total"] >= 3
    before_target = incident_containing(client, TARGET_ID)
    before_count = before_target["confirmed_report_count"]

    request = {
        "text": TEXT,
        "category": "blocked_drain",
        "latitude": 3.08011,
        "longitude": 101.51847,
        "reported_at": "2026-07-11T08:00:00Z",
        "photo_path": None,
    }
    submitted = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "phase9-demo-scenario"},
        json=request,
    )
    replayed = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "phase9-demo-scenario"},
        json=request,
    )
    assert submitted.status_code == 201
    assert replayed.status_code == 201
    assert submitted.json()["created"] is True
    assert replayed.json()["created"] is False
    assert replayed.json()["replayed"] is True
    complaint_id = UUID(submitted.json()["complaint"]["complaint_id"])
    assert len(runtime.repository.list_complaints()) == 121

    review = pending_review_for_pair(client, complaint_id, TARGET_ID)
    approved = client.post(
        f"/api/v1/reviews/{review['review_id']}/approve",
        json={
            "reviewer_id": "demo-officer",
            "note": "Same synthetic school-access drain incident.",
        },
    )
    assert approved.status_code == 200
    payload = approved.json()
    assert payload["final_relationship_state"] == "auto_match"
    assert payload["previous_incident_snapshot_ids"]
    assert payload["new_incident_snapshot_ids"]

    after = incident_containing(client, complaint_id)
    assert str(TARGET_ID) in after["complaint_ids"]
    assert after["confirmed_report_count"] == before_count + 1
    assert after["priority"] is not None
    reasons = after["priority"]["reasons"]
    assert any("multi-report incident" in reason for reason in reasons)
    assert any("safety signal: active_flooding" in reason for reason in reasons)
    assert any("sensitive location" in reason for reason in reasons)
    assert runtime.service.photo_healthcheck is None
