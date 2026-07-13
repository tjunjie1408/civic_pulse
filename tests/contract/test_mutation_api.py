from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from civicpulse.api import AppSettings, create_app
from civicpulse.domain import Category, ClusteringStatus, Complaint, Incident, PriorityLevel
from civicpulse.service import IdempotencyConflict, SeedResult


NOW = datetime(2026, 7, 13, 1, tzinfo=UTC)
COMPLAINT_ID = UUID("00000000-0000-0000-0000-000000000001")
INCIDENT_ID = UUID("10000000-0000-0000-0000-000000000001")


def complaint() -> Complaint:
    return Complaint(
        id=COMPLAINT_ID,
        text="Pothole at Block A",
        normalized_text="pothole at block a",
        category=Category.POTHOLE,
        latitude=3.12,
        longitude=101.68,
        reported_at=NOW,
    )


def incident(status: ClusteringStatus = ClusteringStatus.CONFIRMED) -> Incident:
    return Incident(
        incident_id=INCIDENT_ID,
        complaint_ids=(COMPLAINT_ID,),
        report_count=1,
        confirmed_edges=(),
        review_candidate_ids=(),
        review_candidates=(),
        centroid_latitude=3.12,
        centroid_longitude=101.68,
        radius_metres=0,
        earliest_reported_at=NOW,
        latest_reported_at=NOW,
        category_summary=(Category.POTHOLE,),
        status=status,
        conflict_reasons=("contradictory graph",) if status is ClusteringStatus.CONFLICT else (),
    )


def priority(level: PriorityLevel = PriorityLevel.LOW) -> SimpleNamespace:
    return SimpleNamespace(
        level=level,
        reasons=("default low priority",),
        policy_version="priority-v1",
    )


class FakeMutationService:
    def __init__(
        self,
        *,
        failure: Exception | None = None,
        reset_failure: Exception | None = None,
        incident_status: ClusteringStatus = ClusteringStatus.CONFIRMED,
    ) -> None:
        self.failure = failure
        self.reset_failure = reset_failure
        self.incident_status = incident_status
        self.submissions: list[tuple[object, str]] = []
        self.reset_paths: list[str] = []

    def submit_complaint(self, payload, idempotency_key: str):
        self.submissions.append((payload, idempotency_key))
        if self.failure is not None:
            raise self.failure
        item = complaint()
        current_incident = incident(self.incident_status)
        current_priority = priority(
            PriorityLevel.REVIEW_REQUIRED
            if self.incident_status is ClusteringStatus.CONFLICT
            else PriorityLevel.LOW
        )
        return SimpleNamespace(
            complaint=item,
            incident=current_incident,
            priority=current_priority,
            created=True,
            previous_incident_ids=(),
            current_incident_ids=(INCIDENT_ID,),
            relationship_decisions=(),
            incidents=(current_incident,),
            priorities=(current_priority,),
        )

    def reset_seed(self, path: str) -> SeedResult:
        self.reset_paths.append(path)
        if self.reset_failure is not None:
            raise self.reset_failure
        return SeedResult(
            seed_version="demo-v1",
            content_sha256="a" * 64,
            complaint_count=120,
            incident_ids=tuple(UUID(f"10000000-0000-0000-0000-{index:012d}") for index in range(60)),
            review_ids=(),
            priorities=(),
            review_counts={"pending": 0, "approved": 0, "rejected": 0},
            priority_counts={"low": 20, "medium": 25, "high": 12, "critical": 3},
        )


REQUEST = {
    "text": "Pothole at Block A",
    "latitude": 3.12,
    "longitude": 101.68,
    "reported_at": "2026-07-13T01:00:00Z",
}


def test_submission_maps_service_result_and_snapshot_transition() -> None:
    service = FakeMutationService()
    response = TestClient(create_app(service=service)).post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "opaque-key"},
        json=REQUEST,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["created"] is True
    assert payload["replayed"] is False
    assert payload["incident_transition"] == {
        "previous_incident_snapshot_ids": [],
        "current_incident_snapshot_ids": [str(INCIDENT_ID)],
    }
    assert payload["complaint"]["complaint_id"] == str(COMPLAINT_ID)
    assert service.submissions[0][1] == "opaque-key"


def test_submission_header_validation_is_stable() -> None:
    client = TestClient(create_app(service=FakeMutationService()))

    missing = client.post("/api/v1/complaints", json=REQUEST)
    blank = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "   "},
        json=REQUEST,
    )
    oversized = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "x" * 129},
        json=REQUEST,
    )

    assert missing.status_code == 422
    assert blank.status_code == 422
    assert oversized.status_code == 422
    assert missing.json()["error"]["code"] == "validation_error"


def test_submission_payload_validation_covers_bounds_time_skew_and_strict_fields() -> None:
    client = TestClient(create_app(service=FakeMutationService()))
    invalid_coordinate = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "coordinates"},
        json={**REQUEST, "latitude": 91},
    )
    naive_timestamp = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "naive"},
        json={**REQUEST, "reported_at": "2026-07-13T01:00:00"},
    )
    excessive_future = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "future"},
        json={**REQUEST, "reported_at": (datetime.now(UTC) + timedelta(minutes=6)).isoformat()},
    )
    accepted_skew = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "skew"},
        json={**REQUEST, "reported_at": (datetime.now(UTC) + timedelta(minutes=4)).isoformat()},
    )
    extra_field = client.post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "extra"},
        json={**REQUEST, "unexpected": True},
    )

    assert invalid_coordinate.status_code == 422
    assert naive_timestamp.status_code == 422
    assert excessive_future.status_code == 422
    assert accepted_skew.status_code == 201
    assert extra_field.status_code == 422


def test_submission_conflict_and_unexpected_failure_do_not_leak_details() -> None:
    conflict = TestClient(
        create_app(service=FakeMutationService(failure=IdempotencyConflict("idempotency conflict")))
    ).post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "key"},
        json=REQUEST,
    )
    unexpected = TestClient(create_app(service=FakeMutationService(failure=RuntimeError("SQL / secret path")))).post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "key"},
        json=REQUEST,
    )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert unexpected.status_code == 500
    assert "SQL / secret path" not in unexpected.text


def test_conflict_submission_does_not_expose_operational_priority() -> None:
    response = TestClient(
        create_app(service=FakeMutationService(incident_status=ClusteringStatus.CONFLICT))
    ).post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "conflict"},
        json=REQUEST,
    )

    assert response.status_code == 201
    assert response.json()["incidents"][0]["priority"] is None
    assert response.json()["priorities"] == [None]


def test_reset_is_disabled_by_default() -> None:
    response = TestClient(create_app()).post("/api/v1/admin/reset")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_reset_disabled"


def test_enabled_reset_uses_server_side_seed_path_and_returns_summary() -> None:
    service = FakeMutationService()
    settings = AppSettings(
        admin_reset_enabled=True,
        seed_path="approved/demo-seed.json",
    )
    response = TestClient(create_app(settings=settings, service=service)).post(
        "/api/v1/admin/reset",
        json={"path": "D:/attacker/seed.json"},
    )

    assert response.status_code == 200
    assert service.reset_paths == ["approved/demo-seed.json"]
    assert response.json()["seed_version"] == "demo-v1"
    assert response.json()["complaint_count"] == 120
    assert response.json()["incident_count"] == 60
    assert response.json()["priority_counts"]["critical"] == 3


def test_reset_failure_is_sanitized() -> None:
    service = FakeMutationService(reset_failure=OSError("D:/secret/seed.json"))
    settings = AppSettings(admin_reset_enabled=True, seed_path="approved/demo-seed.json")
    response = TestClient(create_app(settings=settings, service=service)).post("/api/v1/admin/reset")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "seed_configuration_error"
    assert "secret/seed.json" not in response.text


def test_mutation_openapi_is_deterministic_and_reset_has_no_request_body() -> None:
    first = create_app().openapi()
    second = create_app().openapi()

    assert first == second
    assert "/api/v1/complaints" in first["paths"]
    assert "/api/v1/admin/reset" in first["paths"]
    assert "requestBody" not in first["paths"]["/api/v1/admin/reset"]["post"]
