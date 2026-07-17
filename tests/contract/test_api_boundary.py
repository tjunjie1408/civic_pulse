from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from civicpulse.api import create_app
from civicpulse.api.dependencies import get_service
from civicpulse.api.dto.common import GeoPointResponse
from civicpulse.api.dto.complaints import ComplaintCreateRequest, ComplaintResponse
from civicpulse.service import HealthComponent, HealthReport, HealthStatus


def test_complaint_request_normalizes_timezone_and_forbids_extra_fields():
    request = ComplaintCreateRequest.model_validate(
        {
            "text": "Longkang tersumbat",
            "latitude": 3.12,
            "longitude": 101.68,
            "reported_at": "2026-07-13T09:00:00+08:00",
        }
    )

    assert request.reported_at == datetime(2026, 7, 13, 1, tzinfo=timezone.utc)
    assert request.latitude == 3.12
    with pytest.raises(ValueError):
        ComplaintCreateRequest.model_validate(
            {
                "text": "Longkang tersumbat",
                "latitude": 3.12,
                "longitude": 101.68,
                "reported_at": "2026-07-13T01:00:00Z",
                "internal_field": "must be rejected",
            }
        )


def test_api_dtos_do_not_expose_internal_domain_fields():
    assert "normalized_text" not in ComplaintResponse.model_fields
    assert "points" not in ComplaintResponse.model_fields
    assert GeoPointResponse(latitude=3.12, longitude=101.68).model_dump() == {
        "latitude": 3.12,
        "longitude": 101.68,
    }


def test_application_factory_is_side_effect_free_and_openapi_is_stable(monkeypatch):
    monkeypatch.setattr(
        "civicpulse.repository.SQLiteRepository.initialize",
        lambda self: (_ for _ in ()).throw(AssertionError("database I/O during app creation")),
    )
    monkeypatch.setattr(
        "civicpulse.embeddings.SentenceTransformerProvider.__init__",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("model load during app creation")
        ),
    )

    app = create_app()
    schema = app.openapi()
    operation_ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert schema["info"]["version"] == "1.1.0"
    assert "/api/v1/health/live" in schema["paths"]
    assert len(operation_ids) == len(set(operation_ids))


def test_ready_failure_uses_error_envelope_and_dependency_override():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert set(response.json()) == {"error"}
    assert response.json()["error"]["code"] == "readiness_failure"
    assert response.json()["error"]["request_id"]


def test_dependency_override_can_supply_a_fake_health_service():
    component = HealthComponent(status=HealthStatus.HEALTHY, message="ok")
    report = HealthReport(
        status=HealthStatus.HEALTHY,
        core_ready=True,
        database=component,
        policies=component,
        embedding_model=component,
        seed=component,
        photo_provider=component,
    )

    class FakeService:
        def health(self):
            return report

    app = create_app()
    app.dependency_overrides[get_service] = lambda: FakeService()
    response = TestClient(app).get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["core_ready"] is True
