from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from civicpulse.api import create_app
from civicpulse.config import load_priority_policy
from civicpulse.domain import (
    Category,
    ClusteringStatus,
    Complaint,
    Incident,
    MatchState,
    RelationshipDecisionSource,
    RelationshipEdge,
)
from civicpulse.incident_query import IncidentQueryService
from civicpulse.repository import SQLiteRepository

NOW = datetime(2026, 7, 13, 1, tzinfo=UTC)
POLICY = load_priority_policy("config/priority_policy.json")


def complaint(number: int, *, category: Category, hours_ago: int = 1) -> Complaint:
    text = {
        Category.POTHOLE: "Pothole at Block A",
        Category.BLOCKED_DRAIN: "Longkang tersumbat",
    }[category]
    return Complaint(
        id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        text=text,
        normalized_text=text.casefold(),
        category=category,
        latitude=3.12 + number * 0.00001,
        longitude=101.68,
        reported_at=NOW - timedelta(hours=hours_ago),
    )


def incident(
    number: int,
    complaint_item: Complaint,
    *,
    status: ClusteringStatus = ClusteringStatus.CONFIRMED,
) -> Incident:
    return Incident(
        incident_id=UUID(f"10000000-0000-0000-0000-{number:012d}"),
        complaint_ids=(complaint_item.id,),
        report_count=1,
        confirmed_edges=(),
        review_candidate_ids=(),
        review_candidates=(),
        centroid_latitude=complaint_item.latitude,
        centroid_longitude=complaint_item.longitude,
        radius_metres=0,
        earliest_reported_at=complaint_item.reported_at,
        latest_reported_at=complaint_item.reported_at,
        category_summary=(complaint_item.category,),
        status=status,
        conflict_reasons=("contradictory graph",) if status is ClusteringStatus.CONFLICT else (),
    )


class MemoryRepository:
    def __init__(self, complaints: list[Complaint], incidents: list[Incident]) -> None:
        self.complaints = complaints
        self.incidents = incidents

    def list_complaints(self) -> list[Complaint]:
        return self.complaints

    def list_incidents(self) -> list[Incident]:
        return self.incidents

    def get_incident(self, incident_id: UUID) -> Incident | None:
        return next((item for item in self.incidents if item.incident_id == incident_id), None)


def client_for(*, complaints: list[Complaint], incidents: list[Incident]) -> TestClient:
    query_service = IncidentQueryService(
        repository=MemoryRepository(complaints, incidents),
        priority_policy=POLICY,
        now_provider=lambda: NOW,
    )
    return TestClient(create_app(incident_query_service=query_service))


def test_empty_incident_storage_returns_empty_page() -> None:
    response = client_for(complaints=[], incidents=[]).get("/api/v1/incidents")

    assert response.status_code == 200
    assert response.json() == {"items": [], "limit": 50, "offset": 0, "total": 0}


def test_sqlite_snapshot_page_reads_sixty_persisted_incidents(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    complaints = [complaint(number, category=Category.POTHOLE) for number in range(20, 80)]
    incidents = [incident(number, item) for number, item in zip(range(20, 80), complaints)]
    for number, item in enumerate(complaints):
        repository.add_complaint(item, f"seed-{number}")
    repository.replace_incidents(incidents)
    query_service = IncidentQueryService(
        repository=repository,
        priority_policy=POLICY,
        now_provider=lambda: NOW,
    )

    client = TestClient(create_app(incident_query_service=query_service))
    response = client.get("/api/v1/incidents?limit=50&offset=0")
    next_page = client.get("/api/v1/incidents?limit=50&offset=50")

    assert response.status_code == 200
    assert response.json()["total"] == 60
    assert len(response.json()["items"]) == 50
    assert len(next_page.json()["items"]) == 10


def test_list_filters_keep_confirmed_and_pending_counts_separate() -> None:
    pothole = complaint(1, category=Category.POTHOLE)
    drain = complaint(2, category=Category.BLOCKED_DRAIN)
    response = client_for(
        complaints=[pothole, drain],
        incidents=[incident(1, pothole), incident(2, drain)],
    ).get("/api/v1/incidents?category=pothole&limit=1&offset=0")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["category_summary"] == ["pothole"]
    assert payload["items"][0]["confirmed_report_count"] == 1
    assert payload["items"][0]["pending_candidate_count"] == 0


def test_priority_filter_and_pending_candidates_do_not_change_confirmed_count() -> None:
    item = complaint(7, category=Category.POTHOLE)
    candidate_id = UUID("00000000-0000-0000-0000-000000000707")
    confirmed_edge = RelationshipEdge(
        left_id=item.id,
        right_id=item.id,
        decision=MatchState.AUTO_MATCH,
        reasons=("same location",),
        decision_source=RelationshipDecisionSource.AUTOMATED,
    )
    review_edge = RelationshipEdge(
        left_id=item.id,
        right_id=candidate_id,
        decision=MatchState.REVIEW_REQUIRED,
        reasons=("ambiguous wording",),
        decision_source=RelationshipDecisionSource.AUTOMATED,
        matcher_recommendation=MatchState.REVIEW_REQUIRED,
    )
    source = incident(7, item).model_copy(
        update={
            "confirmed_edges": (confirmed_edge,),
            "review_candidate_ids": (candidate_id,),
            "review_candidates": (review_edge,),
        }
    )
    client = client_for(complaints=[item], incidents=[source])

    low = client.get("/api/v1/incidents?priority=low").json()
    high = client.get("/api/v1/incidents?priority=high").json()
    detail = client.get(f"/api/v1/incidents/{source.incident_id}").json()

    assert low["total"] == 1
    assert high["total"] == 0
    assert detail["confirmed_report_count"] == 1
    assert detail["pending_candidate_count"] == 1
    assert detail["confirmed_report_count"] != (
        detail["confirmed_report_count"] + detail["pending_candidate_count"]
    )
    assert detail["confirmed_edges"][0]["decision"] == "auto_match"
    assert detail["review_candidates"][0]["decision"] == "review_required"


def test_incident_order_is_repeatable() -> None:
    first = complaint(8, category=Category.POTHOLE, hours_ago=2)
    second = complaint(9, category=Category.POTHOLE, hours_ago=2)
    client = client_for(
        complaints=[first, second],
        incidents=[incident(9, second), incident(8, first)],
    )

    first_payload = client.get("/api/v1/incidents").json()
    second_payload = client.get("/api/v1/incidents").json()

    assert first_payload == second_payload
    assert [item["incident_id"] for item in first_payload["items"]] == [
        "10000000-0000-0000-0000-000000000008",
        "10000000-0000-0000-0000-000000000009",
    ]


def test_list_incidents_orders_by_priority_then_recency_then_snapshot_id() -> None:
    critical_priority = complaint(41, category=Category.POTHOLE, hours_ago=49)
    high_priority = complaint(42, category=Category.POTHOLE, hours_ago=25)
    medium_latest = complaint(43, category=Category.POTHOLE, hours_ago=6)
    newer_low = complaint(44, category=Category.POTHOLE, hours_ago=1)
    older_low = complaint(45, category=Category.POTHOLE, hours_ago=2)
    tie_first = complaint(46, category=Category.POTHOLE, hours_ago=3)
    tie_second = complaint(47, category=Category.POTHOLE, hours_ago=3)
    medium_earlier = complaint(48, category=Category.POTHOLE, hours_ago=7)
    conflict = complaint(49, category=Category.POTHOLE, hours_ago=0)
    medium_priority = incident(43, medium_latest).model_copy(
        update={
            "complaint_ids": (medium_earlier.id, medium_latest.id),
            "report_count": 2,
            "earliest_reported_at": medium_earlier.reported_at,
        }
    )
    response = client_for(
        complaints=[
            critical_priority,
            high_priority,
            medium_latest,
            newer_low,
            older_low,
            tie_first,
            tie_second,
            medium_earlier,
            conflict,
        ],
        incidents=[
            incident(49, conflict, status=ClusteringStatus.CONFLICT),
            incident(45, older_low),
            incident(47, tie_second),
            medium_priority,
            incident(42, high_priority),
            incident(44, newer_low),
            incident(41, critical_priority),
            incident(46, tie_first),
        ],
    ).get("/api/v1/incidents")

    assert response.status_code == 200
    items = response.json()["items"]
    priority_levels = [
        item["priority"]["level"] if item["priority"] is not None else None for item in items
    ]
    assert priority_levels == [
        "critical",
        "high",
        "medium",
        "low",
        "low",
        "low",
        "low",
        None,
    ]
    assert [item["incident_id"] for item in items] == [
        "10000000-0000-0000-0000-000000000041",
        "10000000-0000-0000-0000-000000000042",
        "10000000-0000-0000-0000-000000000043",
        "10000000-0000-0000-0000-000000000044",
        "10000000-0000-0000-0000-000000000045",
        "10000000-0000-0000-0000-000000000046",
        "10000000-0000-0000-0000-000000000047",
        "10000000-0000-0000-0000-000000000049",
    ]


def test_conflict_detail_has_null_priority_and_exposes_snapshot_evidence() -> None:
    item = complaint(3, category=Category.POTHOLE)
    conflict = incident(3, item, status=ClusteringStatus.CONFLICT)
    response = client_for(complaints=[item], incidents=[conflict]).get(
        f"/api/v1/incidents/{conflict.incident_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["incident_id"] == str(conflict.incident_id)
    assert payload["priority"] is None
    assert payload["conflict_reasons"] == ["contradictory graph"]
    assert payload["complaint_ids"] == [str(item.id)]
    assert payload["confirmed_edges"] == []
    assert payload["review_candidates"] == []


def test_incident_detail_returns_bounded_confirmed_report_summaries() -> None:
    complaints = [complaint(number, category=Category.POTHOLE) for number in range(1, 6)]
    source = incident(1, complaints[0]).model_copy(
        update={
            "complaint_ids": tuple(item.id for item in complaints),
            "report_count": len(complaints),
            "earliest_reported_at": complaints[0].reported_at,
            "latest_reported_at": complaints[-1].reported_at,
        }
    )
    client = client_for(complaints=complaints, incidents=[source])

    response = client.get(f"/api/v1/incidents/{source.incident_id}")

    assert response.status_code == 200
    preview = response.json()["confirmed_reports"]
    assert preview["total"] == 5
    assert preview["has_more"] is True
    assert len(preview["items"]) == 3
    assert [item["complaint_id"] for item in preview["items"]] == [
        str(item.id) for item in complaints[:3]
    ]
    assert preview["items"][0] == {
        "complaint_id": str(complaints[0].id),
        "text": complaints[0].text,
        "category": "pothole",
        "latitude": complaints[0].latitude,
        "longitude": complaints[0].longitude,
        "reported_at": complaints[0].reported_at.isoformat().replace("+00:00", "Z"),
        "photo_available": False,
    }
    assert "photo_path" not in response.text


def test_missing_snapshot_uses_stable_not_found_error_envelope() -> None:
    missing_id = "10000000-0000-0000-0000-999999999999"
    response = client_for(complaints=[], incidents=[]).get(f"/api/v1/incidents/{missing_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "incident_not_found"
    assert response.json()["error"]["details"] == {"incident_id": missing_id}
    assert response.json()["error"]["request_id"]


def test_limit_bounds_and_utc_timestamps_are_enforced() -> None:
    item = complaint(4, category=Category.POTHOLE)
    client = client_for(complaints=[item], incidents=[incident(4, item)])

    assert client.get("/api/v1/incidents?limit=0").status_code == 422
    assert client.get("/api/v1/incidents?limit=101").status_code == 422
    assert client.get("/api/v1/incidents?offset=-1").status_code == 422
    response = client.get("/api/v1/incidents/10000000-0000-0000-0000-000000000004")
    assert response.json()["earliest_reported_at"].endswith("Z")


def test_openapi_has_unique_incident_operation_ids_and_health_routes_remain() -> None:
    app = create_app()
    schema = app.openapi()
    assert schema == create_app().openapi()
    operations = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert "/api/v1/incidents" in schema["paths"]
    assert "/api/v1/incidents/{incident_id}" in schema["paths"]
    assert "/api/v1/health/live" in schema["paths"]
    assert "/api/v1/health/ready" in schema["paths"]
    assert len(operations) == len(set(operations))
