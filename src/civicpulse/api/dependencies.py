"""Request dependencies kept separate for test overrides and future adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from fastapi import Depends, Request

from civicpulse.api.errors import ApiError
from civicpulse.incident_query import IncidentQueryService
from civicpulse.service import CivicPulseService, HealthReport


def get_service(request: Request) -> CivicPulseService:
    service = getattr(request.app.state, "service", None)
    if service is None:
        raise ApiError(
            code="readiness_failure",
            message="Application services are not configured.",
            status_code=503,
        )
    return cast(CivicPulseService, service)


def get_health_service(
    request: Request,
    service: CivicPulseService = Depends(get_service),  # noqa: B008
) -> Callable[[], HealthReport]:
    configured = getattr(request.app.state, "health_service", None)
    if configured is not None:
        return cast(Callable[[], HealthReport], configured)
    return service.health


def get_incident_query_service(
    request: Request,
) -> IncidentQueryService:
    configured = getattr(request.app.state, "incident_query_service", None)
    if configured is not None:
        return cast(IncidentQueryService, configured)
    service = getattr(request.app.state, "service", None)
    if service is None:
        raise ApiError(
            code="readiness_failure",
            message="Application services are not configured.",
            status_code=503,
        )
    service = cast(CivicPulseService, service)
    return IncidentQueryService(
        repository=service.repository,
        priority_policy=service.priority_policy,
        sensitive_locations=service.sensitive_locations,
    )
