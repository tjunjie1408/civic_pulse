import json
from pathlib import Path
from typing import Any

from civicpulse.api import create_app
from civicpulse.domain import Category
from scripts.openapi_snapshot import canonical_json, canonicalize_openapi
from tests.contract.test_incident_read_api import client_for, complaint, incident

ROOT = Path(__file__).parents[2]
SNAPSHOT = ROOT / "tests" / "contracts" / "openapi-v1.json"
EXPECTED_PATHS = {
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/incidents",
    "/api/v1/incidents/{incident_id}",
    "/api/v1/complaints",
    "/api/v1/admin/reset",
    "/api/v1/photos",
    "/api/v1/photos/{photo_id}",
    "/api/v1/reviews",
    "/api/v1/reviews/{review_id}",
    "/api/v1/reviews/{review_id}/approve",
    "/api/v1/reviews/{review_id}/reject",
}


def document() -> dict[str, Any]:
    return canonicalize_openapi(create_app().openapi())


def response_schema(operation: dict[str, Any], status_code: str) -> dict[str, Any]:
    return operation["responses"][status_code]["content"]["application/json"]["schema"]


def error_response_codes(operation: dict[str, Any]) -> set[str]:
    return {
        code
        for code in operation["responses"]
        if code.startswith("4") or code.startswith("5")
    }


def assert_error_schema(operation: dict[str, Any], status_code: str) -> None:
    schema = response_schema(operation, status_code)
    assert schema["$ref"].endswith("/ApiErrorResponse")


def test_openapi_matches_committed_canonical_snapshot() -> None:
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert document() == expected


def test_openapi_is_byte_identical_across_repeated_app_creation() -> None:
    first = canonical_json(create_app().openapi())
    second = canonical_json(create_app().openapi())

    assert first == second


def test_openapi_metadata_paths_and_operation_ids_are_frozen() -> None:
    payload = document()
    operations = [
        operation
        for path in payload["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert payload["info"] == {"title": "CivicPulse-lite API", "version": "1.1.0"}
    assert set(payload["paths"]) == EXPECTED_PATHS
    assert all(path.startswith("/api/v1/") for path in payload["paths"])
    assert len({operation["operationId"] for operation in operations}) == len(operations)


def test_complaint_submission_contract_preserves_header_and_errors() -> None:
    operation = document()["paths"]["/api/v1/complaints"]["post"]
    header = next(
        parameter
        for parameter in operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )

    assert header["in"] == "header"
    assert header["required"] is True
    assert header["schema"]["type"] == "string"
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ComplaintCreateRequest"
    )
    assert {"409", "422", "500"}.issubset(error_response_codes(operation))
    assert_error_schema(operation, "409")


def test_photo_fetch_contract_preserves_binary_media_and_errors() -> None:
    operation = document()["paths"]["/api/v1/photos/{photo_id}"]["get"]
    success_content = operation["responses"]["200"]["content"]

    assert set(success_content) == {"image/jpeg", "image/png"}
    for media_type in success_content.values():
        assert media_type["schema"] == {"format": "binary", "type": "string"}
    assert {"404", "422"}.issubset(error_response_codes(operation))
    assert_error_schema(operation, "404")
    assert_error_schema(operation, "422")


def test_review_resolution_contract_preserves_payload_errors_and_transition_fields() -> None:
    payload = document()
    schema = payload["components"]["schemas"]["ReviewMutationResponse"]
    approve = payload["paths"]["/api/v1/reviews/{review_id}/approve"]["post"]
    reject = payload["paths"]["/api/v1/reviews/{review_id}/reject"]["post"]

    request_ref = approve["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert request_ref.endswith("/ReviewResolutionRequest")
    assert {"404", "409", "422", "500"}.issubset(error_response_codes(approve))
    assert {"404", "409", "422", "500"}.issubset(error_response_codes(reject))
    assert schema["required"]
    assert {
        "review",
        "final_relationship_state",
        "affected_complaint_ids",
        "previous_incident_snapshot_ids",
        "new_incident_snapshot_ids",
        "affected_incidents",
        "resulting_priorities",
        "conflict_status",
    }.issubset(schema["properties"])
    assert_error_schema(approve, "404")
    assert_error_schema(approve, "409")


def test_conflict_priority_is_nullable_without_assuming_generator_shape() -> None:
    priority = document()["components"]["schemas"]["IncidentSummaryResponse"]["properties"][
        "priority"
    ]

    nullable_any_of = any(option.get("type") == "null" for option in priority.get("anyOf", []))
    assert nullable_any_of or priority.get("type") == ["object", "null"]


def test_admin_reset_is_documented_as_disabled_and_has_no_client_path() -> None:
    operation = document()["paths"]["/api/v1/admin/reset"]["post"]

    assert "requestBody" not in operation
    assert {"403", "500", "503"}.issubset(error_response_codes(operation))
    assert_error_schema(operation, "403")
    assert "path" not in json.dumps(operation)
    assert "url" not in json.dumps(operation)


def test_strict_request_schemas_and_error_envelope_are_frozen() -> None:
    schemas = document()["components"]["schemas"]

    assert schemas["ComplaintCreateRequest"]["additionalProperties"] is False
    assert schemas["ReviewResolutionRequest"]["additionalProperties"] is False
    error = schemas["ApiErrorResponse"]
    assert error["properties"]["error"]["$ref"].endswith("/ApiErrorBody")


def test_openapi_date_time_format_and_runtime_incident_timestamp_are_separate_contracts() -> None:
    schemas = document()["components"]["schemas"]
    incident_schema = schemas["IncidentSummaryResponse"]
    for field in ("earliest_reported_at", "latest_reported_at"):
        assert incident_schema["properties"][field]["format"] == "date-time"

    item = complaint(40, category=Category.POTHOLE)
    response = client_for(complaints=[item], incidents=[incident(40, item)]).get(
        "/api/v1/incidents/10000000-0000-0000-0000-000000000040"
    )

    assert response.status_code == 200
    assert response.json()["earliest_reported_at"].endswith("Z")
    assert response.json()["latest_reported_at"].endswith("Z")
