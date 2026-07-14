"""Complaint submission and protected deterministic reset endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from pydantic import ValidationError

from civicpulse.api.dependencies import (
    AppSettingsProtocol,
    get_app_settings,
    get_optional_service,
    get_service,
)
from civicpulse.api.dto.common import ApiErrorResponse
from civicpulse.api.dto.complaints import ComplaintCreateRequest, ComplaintResponse
from civicpulse.api.dto.incidents import IncidentSummaryResponse, PriorityResponse
from civicpulse.api.dto.mutations import (
    ComplaintSubmissionResponse,
    IncidentTransitionResponse,
    SeedResetResponse,
)
from civicpulse.api.errors import ApiError
from civicpulse.api.routes.incidents import to_edge_response, to_incident_summary
from civicpulse.domain import (
    Category,
    ClusteringStatus,
    Complaint,
    ComplaintInput,
    PriorityAssessment,
    SubmissionResult,
)
from civicpulse.incident_query import IncidentRead
from civicpulse.repository import DatabaseBusy
from civicpulse.service import CivicPulseService, IdempotencyConflict, SeedResult

router = APIRouter(tags=["mutations"])


def _complaint_response(complaint: Complaint) -> ComplaintResponse:
    return ComplaintResponse(
        complaint_id=complaint.id,
        text=complaint.text,
        category=complaint.category or Category.OTHER,
        latitude=complaint.latitude,
        longitude=complaint.longitude,
        reported_at=complaint.reported_at,
        photo_path=complaint.photo_path,
    )


def _priority_response(priority: PriorityAssessment) -> PriorityResponse:
    return PriorityResponse(
        level=priority.level,
        reasons=list(priority.reasons),
        policy_version=priority.policy_version,
    )


def _submission_response(result: SubmissionResult) -> ComplaintSubmissionResponse:
    priorities = list(result.priorities)
    incident_summaries: list[IncidentSummaryResponse] = []
    priority_responses: list[PriorityResponse | None] = []
    for index, incident in enumerate(result.incidents):
        priority = priorities[index] if index < len(priorities) else None
        operational_priority = None if incident.status is ClusteringStatus.CONFLICT else priority
        policy_version = "" if operational_priority is None else operational_priority.policy_version
        incident_summaries.append(
            to_incident_summary(
                IncidentRead(
                    incident=incident,
                    priority=operational_priority,
                    policy_version=policy_version,
                )
            )
        )
        priority_responses.append(
            None if operational_priority is None else _priority_response(operational_priority)
        )
    return ComplaintSubmissionResponse(
        complaint=_complaint_response(result.complaint),
        created=result.created,
        replayed=not result.created,
        relationship_decisions=[to_edge_response(edge) for edge in result.relationship_decisions],
        incident_transition=IncidentTransitionResponse(
            previous_incident_snapshot_ids=list(result.previous_incident_ids),
            current_incident_snapshot_ids=list(result.current_incident_ids),
        ),
        incidents=incident_summaries,
        priorities=priority_responses,
    )


@router.post(
    "/complaints",
    response_model=ComplaintSubmissionResponse,
    status_code=201,
    operation_id="complaintsCreate",
    description="Submit a complaint through the application mutation service.",
    responses={
        409: {"model": ApiErrorResponse, "description": "Idempotency conflict."},
        422: {"model": ApiErrorResponse, "description": "Request validation failed."},
        500: {"model": ApiErrorResponse, "description": "Internal server error."},
    },
)
def submit_complaint(
    request: ComplaintCreateRequest,
    service: CivicPulseService = Depends(get_service),  # noqa: B008
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
) -> ComplaintSubmissionResponse:
    key = idempotency_key.strip()
    if not key:
        raise ApiError(
            code="validation_error",
            message="Request validation failed.",
            status_code=422,
            details={"field": "Idempotency-Key"},
        )
    try:
        payload = ComplaintInput.model_validate(request.model_dump())
    except ValidationError as exc:
        raise ApiError(
            code="validation_error",
            message="Request validation failed.",
            status_code=422,
            details={"error_count": len(exc.errors())},
        ) from exc
    try:
        result = service.submit_complaint(payload, key)
    except IdempotencyConflict as exc:
        raise ApiError(
            code="idempotency_conflict",
            message="The Idempotency-Key was reused with a different request.",
            status_code=409,
        ) from exc
    except DatabaseBusy as exc:
        raise ApiError(
            code="database_busy",
            message="The local database is busy; retry the operation.",
            status_code=503,
        ) from exc
    except Exception as exc:
        raise ApiError(
            code="internal_error",
            message="An unexpected internal error occurred.",
            status_code=500,
        ) from exc
    return _submission_response(result)


@router.post(
    "/admin/reset",
    response_model=SeedResetResponse,
    operation_id="adminReset",
    description="Admin operation: restore the server-configured demo seed; disabled by default.",
    responses={
        403: {"model": ApiErrorResponse, "description": "Administrative reset is disabled."},
        500: {"model": ApiErrorResponse, "description": "Internal server error."},
        503: {"model": ApiErrorResponse, "description": "Seed configuration is unavailable."},
    },
)
def reset_seed(
    service: CivicPulseService | None = Depends(get_optional_service),  # noqa: B008
    settings: AppSettingsProtocol = Depends(get_app_settings),  # noqa: B008
) -> SeedResetResponse:
    if not settings.admin_reset_enabled:
        raise ApiError(
            code="admin_reset_disabled",
            message="Administrative reset is disabled.",
            status_code=403,
        )
    if service is None:
        raise ApiError(
            code="readiness_failure",
            message="Application services are not configured.",
            status_code=503,
        )
    try:
        result = service.reset_seed(settings.seed_path)
    except DatabaseBusy as exc:
        raise ApiError(
            code="database_busy",
            message="The local database is busy; retry the operation.",
            status_code=503,
        ) from exc
    except (OSError, ValueError) as exc:
        raise ApiError(
            code="seed_configuration_error",
            message="The configured seed could not be loaded.",
            status_code=503,
        ) from exc
    except Exception as exc:
        raise ApiError(
            code="internal_error",
            message="An unexpected internal error occurred.",
            status_code=500,
        ) from exc
    return _reset_response(result)


def _reset_response(result: SeedResult) -> SeedResetResponse:
    return SeedResetResponse(
        seed_version=result.seed_version,
        seed_checksum=result.content_sha256,
        complaint_count=result.complaint_count,
        incident_count=len(result.incident_ids),
        review_counts=result.review_counts,
        priority_counts=result.priority_counts,
    )
