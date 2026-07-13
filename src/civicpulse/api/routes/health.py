"""Liveness and readiness endpoints."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends

from civicpulse.api.dependencies import get_health_service
from civicpulse.api.dto.common import LiveResponse
from civicpulse.api.dto.health import HealthResponse
from civicpulse.api.errors import ApiError
from civicpulse.service import HealthReport

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LiveResponse, operation_id="healthLive")
def live() -> LiveResponse:
    return LiveResponse()


@router.get("/ready", response_model=HealthResponse, operation_id="healthReady")
def ready(
    health_service: Callable[[], HealthReport] = Depends(get_health_service),  # noqa: B008
) -> HealthResponse:
    report = health_service()
    if not report.core_ready:
        raise ApiError(
            code="readiness_failure",
            message="Core application dependencies are not ready.",
            status_code=503,
            details={"status": report.status.value},
        )
    return HealthResponse.from_domain(report)
