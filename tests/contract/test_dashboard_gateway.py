"""Contract tests for the dashboard's HTTP-only boundary."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import (
    ApiErrorResponse,
    GeoPointResponse,
    HealthComponentResponse,
    HealthResponse,
    IncidentListResponse,
    IncidentSummaryResponse,
    LiveResponse,
    PriorityResponse,
)
from civicpulse_dashboard.ui.operational_queue import queue_rows

ROOT = Path(__file__).parents[2]
OPENAPI = ROOT / "tests" / "contracts" / "openapi-v1.json"


def _incident(
    incident_id: str,
    *,
    status: str = "confirmed",
    priority: str | None = "high",
) -> dict[str, object]:
    return {
        "incident_id": incident_id,
        "status": status,
        "category_summary": ["pothole"],
        "priority": (
            None
            if priority is None
            else {"level": priority, "reasons": ["test"], "policy_version": "v1"}
        ),
        "confirmed_report_count": 2,
        "pending_candidate_count": 1,
        "centroid": {"latitude": 1.3, "longitude": 103.8},
        "radius_metres": 12.5,
        "earliest_reported_at": "2026-07-13T00:00:00Z",
        "latest_reported_at": "2026-07-13T01:00:00Z",
        "conflict_reasons": ["contradictory evidence"] if status == "conflict" else [],
    }


def _page(*items: dict[str, object]) -> dict[str, object]:
    return {"items": list(items), "limit": 50, "offset": 0, "total": len(items)}


def test_dashboard_models_match_frozen_incident_contract() -> None:
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    schemas = document["components"]["schemas"]

    for model, schema_name in (
        (IncidentSummaryResponse, "IncidentSummaryResponse"),
        (IncidentListResponse, "IncidentListResponse"),
        (PriorityResponse, "PriorityResponse"),
        (GeoPointResponse, "GeoPointResponse"),
    ):
        schema = schemas[schema_name]
        assert set(model.model_fields) == set(schema["properties"])
        assert list(model.model_fields) == schema["required"]
        assert model.model_config["extra"] == "forbid"

    assert schemas["PriorityLevel"]["enum"] == [
        "critical",
        "high",
        "medium",
        "low",
        "review_required",
    ]
    assert schemas["ClusteringStatus"]["enum"] == ["confirmed", "isolated", "conflict"]
    assert schemas["Category"]["enum"] == [
        "pothole",
        "blocked_drain",
        "flooding",
        "rubbish",
        "street_light",
        "other",
    ]


def test_error_envelope_is_strict_and_matches_frozen_contract() -> None:
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    schemas = document["components"]["schemas"]
    for model, schema_name in (
        (ApiErrorResponse, "ApiErrorResponse"),
        (HealthComponentResponse, "HealthComponentResponse"),
        (HealthResponse, "HealthResponse"),
    ):
        schema = schemas[schema_name]
        generated = model.model_json_schema()
        assert set(model.model_fields) == set(schema["properties"])
        assert generated["required"] == schema["required"]
        assert model.model_config["extra"] == "forbid"

    assert set(schemas["ApiErrorBody"]["properties"]) == {
        "code",
        "message",
        "details",
        "request_id",
    }
    assert ApiErrorResponse.model_config["extra"] == "forbid"
    with pytest.raises(ValueError):
        ApiErrorResponse.model_validate({"error": {"code": "x"}, "traceback": "secret"})


def test_gateway_preserves_api_order_and_sends_filters() -> None:
    first = str(UUID("00000000-0000-0000-0000-000000000001"))
    second = str(UUID("00000000-0000-0000-0000-000000000002"))
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_page(_incident(first), _incident(second, priority="low")))

    with ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client:
        page = client.list_incidents(
            limit=2,
            offset=4,
            status="confirmed",
            priority="high",
            category="pothole",
        )

    assert [item.incident_id for item in page.items] == [UUID(first), UUID(second)]
    assert requests[0].url.path == "/api/v1/incidents"
    assert dict(requests[0].url.params) == {
        "status": "confirmed",
        "priority": "high",
        "category": "pothole",
        "limit": "2",
        "offset": "4",
    }


def test_gateway_classifies_readiness_errors_without_leaking_server_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "error": {
                    "code": "readiness_failure",
                    "message": "Application services are not configured.",
                    "details": {"path": "C:/private/model-cache", "sql": "SELECT secret"},
                    "request_id": "request-1",
                }
            },
        )

    with (
        ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(DashboardApiError) as raised,
    ):
        client.list_incidents()

    error = raised.value
    assert error.status_code == 503
    assert error.code == "readiness_failure"
    assert "C:/private" not in error.user_message
    assert "SELECT" not in error.user_message


def test_gateway_maps_unreachable_api_to_safe_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("socket details", request=request)

    with (
        ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(DashboardApiError) as raised,
    ):
        client.list_incidents()

    assert raised.value.code == "api_unreachable"
    assert raised.value.status_code == 0
    assert "socket details" not in raised.value.user_message


def test_gateway_parses_legal_liveness_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "alive"})

    with ApiClient("http://api.test/api/v1", transport=httpx.MockTransport(handler)) as client:
        response = client.health_live()

    assert response == LiveResponse()


def test_queue_rows_keep_api_order_and_separate_conflict_priority() -> None:
    page = IncidentListResponse.model_validate(
        _page(
            _incident("00000000-0000-0000-0000-000000000001", priority="high"),
            _incident("00000000-0000-0000-0000-000000000002", status="conflict", priority=None),
        )
    )

    rows = queue_rows(page)

    assert [row["incident_id"] for row in rows] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]
    assert rows[0]["confirmed_reports"] == 2
    assert rows[0]["pending_candidates"] == 1
    assert rows[1]["priority"] == "No operational priority"


def test_dashboard_package_does_not_import_backend_internals() -> None:
    package = ROOT / "src" / "civicpulse_dashboard"
    forbidden_prefixes = ("civicpulse.",)
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any(name.startswith(forbidden_prefixes) for name in names), path
