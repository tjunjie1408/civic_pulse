import httpx
import pytest

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError


def _ready_payload() -> dict[str, object]:
    component = {"status": "healthy", "message": "ok", "recovery_command": None}
    return {
        "status": "healthy",
        "core_ready": True,
        "database": component,
        "policies": component,
        "embedding_model": component,
        "seed": component,
        "photo_provider": {"status": "degraded", "message": "optional", "recovery_command": None},
    }


def test_dashboard_maps_cache_not_ready_without_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "error": {
                    "code": "readiness_failure",
                    "message": "The embedding model is unavailable or not cached.",
                    "details": {"path": "C:/private/model-cache"},
                    "request_id": "request-1",
                }
            },
        )

    with (
        ApiClient(
            "http://api.test/api/v1", transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(DashboardApiError) as caught,
    ):
        client.health_ready()

    assert caught.value.code == "readiness_failure"
    assert "C:/private" not in caught.value.user_message
    assert "model-cache" not in caught.value.user_message


def test_dashboard_keeps_unreachable_behavior() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline socket details", request=request)

    with (
        ApiClient(
            "http://api.test/api/v1", transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(DashboardApiError) as caught,
    ):
        client.health_ready()

    assert caught.value.code == "api_unreachable"
    assert caught.value.status_code == 0
    assert "offline socket details" not in caught.value.user_message


def test_dashboard_recovers_after_readiness_becomes_healthy() -> None:
    responses = [
        httpx.Response(
            503,
            json={
                "error": {
                    "code": "readiness_failure",
                    "message": "not ready",
                    "details": {},
                    "request_id": "request-1",
                }
            },
        ),
        httpx.Response(200, json=_ready_payload()),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    with ApiClient(
        "http://api.test/api/v1", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(DashboardApiError):
            client.health_ready()
        recovered = client.health_ready()

    assert recovered.core_ready is True
