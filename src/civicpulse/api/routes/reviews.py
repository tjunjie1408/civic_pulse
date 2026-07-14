"""Review read and resolution endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from civicpulse.api.dependencies import get_service
from civicpulse.api.dto.common import ApiErrorResponse
from civicpulse.api.dto.complaints import ComplaintResponse
from civicpulse.api.dto.incidents import IncidentSummaryResponse, PriorityResponse
from civicpulse.api.dto.reviews import (
    LocationEntityResponse,
    ReviewDetailResponse,
    ReviewEvidenceResponse,
    ReviewListResponse,
    ReviewMutationResponse,
    ReviewResolutionRequest,
    ReviewSummaryResponse,
)
from civicpulse.api.errors import ApiError
from civicpulse.api.routes.incidents import to_incident_summary
from civicpulse.domain import (
    Category,
    ClusteringStatus,
    Complaint,
    Incident,
    LocationEntity,
    PriorityAssessment,
    ReviewRead,
    ReviewRecord,
    ReviewStatus,
)
from civicpulse.incident_query import IncidentRead
from civicpulse.service import (
    CivicPulseService,
    ReviewAlreadyResolved,
    ReviewNotFound,
    ReviewStale,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


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


def _summary(view: ReviewRead) -> ReviewSummaryResponse:
    record = view.review
    return ReviewSummaryResponse(
        review_id=record.review_id,
        left_complaint_id=record.left_id,
        right_complaint_id=record.right_id,
        original_matcher_recommendation=record.matcher_recommendation,
        matcher_reasons=list(record.matcher_reasons),
        status=record.status,
        created_at=record.created_at,
        resolved_at=record.resolved_at,
        reviewer_id=record.reviewed_by,
        review_note=record.review_note,
        final_relationship_state=record.final_relationship_state,
        decision_source=record.decision_source,
        graph_version=record.graph_version_at_creation,
    )


def _evidence(record: ReviewRecord) -> ReviewEvidenceResponse | None:
    evidence = record.matcher_evidence
    if evidence is None:
        return None

    def location_entity_payload(item: LocationEntity) -> dict[str, object]:
        return item.model_dump(mode="json")

    return ReviewEvidenceResponse(
        semantic_similarity=evidence.semantic_similarity,
        geo_distance_metres=evidence.distance_metres,
        time_difference_seconds=evidence.time_gap_seconds,
        category_compatibility=evidence.category_compatible,
        location_compatibility=evidence.location_compatibility,
        first_location_entities=[
            LocationEntityResponse.model_validate(location_entity_payload(item))
            for item in evidence.first_location_entities
        ],
        second_location_entities=[
            LocationEntityResponse.model_validate(location_entity_payload(item))
            for item in evidence.second_location_entities
        ],
    )


def _detail(
    view: ReviewRead,
    *,
    previous_incident_ids: tuple[UUID, ...] = (),
    new_incident_ids: tuple[UUID, ...] = (),
) -> ReviewDetailResponse:
    record = view.review
    return ReviewDetailResponse(
        review_id=record.review_id,
        status=record.status,
        complaint_a=_complaint_response(view.complaint_a),
        complaint_b=_complaint_response(view.complaint_b),
        original_matcher_recommendation=record.matcher_recommendation,
        matcher_reasons=list(record.matcher_reasons),
        matcher_evidence=_evidence(record),
        created_at=record.created_at,
        resolved_at=record.resolved_at,
        reviewer_id=record.reviewed_by,
        review_note=record.review_note,
        final_relationship_state=record.final_relationship_state,
        decision_source=record.decision_source,
        graph_version=record.graph_version_at_creation,
        previous_incident_snapshot_ids=list(previous_incident_ids),
        new_incident_snapshot_ids=list(new_incident_ids),
    )


def _sort_key(view: ReviewRead) -> tuple[int, float, str]:
    record = view.review
    if record.status is ReviewStatus.PENDING:
        return 0, record.created_at.timestamp(), str(record.review_id)
    resolved_at = record.resolved_at or datetime.min.replace(tzinfo=UTC)
    return 1, -resolved_at.timestamp(), str(record.review_id)


def _incident_summary(
    incident: Incident,
    priority: PriorityAssessment | None,
) -> IncidentSummaryResponse:
    operational_priority = None if incident.status is ClusteringStatus.CONFLICT else priority
    policy_version = "" if operational_priority is None else operational_priority.policy_version
    return to_incident_summary(
        IncidentRead(
            incident=incident,
            priority=operational_priority,
            policy_version=policy_version,
        )
    )


def _priority_response(priority: PriorityAssessment | None) -> PriorityResponse | None:
    if priority is None:
        return None
    return PriorityResponse(
        level=priority.level,
        reasons=list(priority.reasons),
        policy_version=priority.policy_version,
    )


@router.get(
    "",
    response_model=ReviewListResponse,
    operation_id="reviewsList",
    responses={422: {"model": ApiErrorResponse, "description": "Request validation failed."}},
)
def list_reviews(
    service: CivicPulseService = Depends(get_service),  # noqa: B008
    status: ReviewStatus | None = Query(default=None),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReviewListResponse:
    views = sorted(service.list_reviews(status), key=_sort_key)
    page = views[offset : offset + limit]
    return ReviewListResponse(
        items=[_summary(view) for view in page],
        limit=limit,
        offset=offset,
        total=len(views),
    )


@router.get(
    "/{review_id}",
    response_model=ReviewDetailResponse,
    operation_id="reviewDetail",
    responses={
        404: {"model": ApiErrorResponse, "description": "Review not found."},
        422: {"model": ApiErrorResponse, "description": "Request validation failed."},
    },
)
def get_review(
    review_id: UUID,
    service: CivicPulseService = Depends(get_service),  # noqa: B008
) -> ReviewDetailResponse:
    view = service.get_review(review_id)
    if view is None:
        raise ApiError(
            code="review_not_found",
            message="The requested review was not found.",
            status_code=404,
            details={"review_id": str(review_id)},
        )
    return _detail(view)


def _resolve(
    review_id: UUID,
    request: ReviewResolutionRequest,
    service: CivicPulseService,
    *,
    approve: bool,
) -> ReviewMutationResponse:
    try:
        result = service.resolve_review(
            review_id,
            approve=approve,
            reviewer_id=request.reviewer_id,
            note=request.note,
        )
    except ReviewNotFound as exc:
        raise ApiError(
            code="review_not_found",
            message="The requested review was not found.",
            status_code=404,
        ) from exc
    except ReviewAlreadyResolved as exc:
        raise ApiError(
            code="review_already_resolved",
            message="The review has already been resolved.",
            status_code=409,
        ) from exc
    except ReviewStale as exc:
        raise ApiError(
            code="review_stale",
            message="The review graph is stale and must be reloaded.",
            status_code=409,
        ) from exc
    except Exception as exc:
        raise ApiError(
            code="internal_error",
            message="An unexpected internal error occurred.",
            status_code=500,
        ) from exc
    if result.review is None:
        raise ApiError(
            code="internal_error",
            message="The review resolution returned no review record.",
            status_code=500,
        )
    view = service.get_review(result.review.review_id)
    if view is None:
        raise ApiError(
            code="internal_error",
            message="The resolved review could not be reloaded.",
            status_code=500,
        )
    priorities = list(result.resulting_priorities)
    affected_incidents = list(result.affected_incidents)
    return ReviewMutationResponse(
        review=_detail(
            view,
            previous_incident_ids=result.previous_incident_ids,
            new_incident_ids=result.new_incident_ids,
        ),
        final_relationship_state=result.final_relationship_state,
        affected_complaint_ids=list(result.affected_complaint_ids),
        previous_incident_snapshot_ids=list(result.previous_incident_ids),
        new_incident_snapshot_ids=list(result.new_incident_ids),
        affected_incidents=[
            _incident_summary(incident, priorities[index] if index < len(priorities) else None)
            for index, incident in enumerate(affected_incidents)
        ],
        resulting_priorities=[
            None
            if index >= len(affected_incidents)
            or affected_incidents[index].status is ClusteringStatus.CONFLICT
            else _priority_response(priority)
            for index, priority in enumerate(priorities)
        ],
        conflict_status=result.conflict_status,
    )


@router.post(
    "/{review_id}/approve",
    response_model=ReviewMutationResponse,
    operation_id="reviewApprove",
    responses={
        404: {"model": ApiErrorResponse, "description": "Review not found."},
        409: {"model": ApiErrorResponse, "description": "Review cannot be resolved."},
        422: {"model": ApiErrorResponse, "description": "Request validation failed."},
        500: {"model": ApiErrorResponse, "description": "Internal server error."},
    },
)
def approve_review(
    review_id: UUID,
    request: ReviewResolutionRequest,
    service: CivicPulseService = Depends(get_service),  # noqa: B008
) -> ReviewMutationResponse:
    return _resolve(review_id, request, service, approve=True)


@router.post(
    "/{review_id}/reject",
    response_model=ReviewMutationResponse,
    operation_id="reviewReject",
    responses={
        404: {"model": ApiErrorResponse, "description": "Review not found."},
        409: {"model": ApiErrorResponse, "description": "Review cannot be resolved."},
        422: {"model": ApiErrorResponse, "description": "Request validation failed."},
        500: {"model": ApiErrorResponse, "description": "Internal server error."},
    },
)
def reject_review(
    review_id: UUID,
    request: ReviewResolutionRequest,
    service: CivicPulseService = Depends(get_service),  # noqa: B008
) -> ReviewMutationResponse:
    return _resolve(review_id, request, service, approve=False)
