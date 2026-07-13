"""Read-only incident snapshot endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from civicpulse.api.dependencies import get_incident_query_service
from civicpulse.api.dto.common import GeoPointResponse
from civicpulse.api.dto.incidents import (
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentSummaryResponse,
    PriorityResponse,
    RelationshipEdgeResponse,
    ReviewCandidateResponse,
)
from civicpulse.api.errors import ApiError
from civicpulse.domain import Category, ClusteringStatus, PriorityLevel, RelationshipEdge
from civicpulse.incident_query import IncidentListQuery, IncidentQueryService, IncidentRead

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _priority(read: IncidentRead) -> PriorityResponse | None:
    if read.priority is None:
        return None
    return PriorityResponse(
        level=read.priority.level,
        reasons=list(read.priority.reasons),
        policy_version=read.policy_version,
    )


def _edge_response(edge: RelationshipEdge) -> RelationshipEdgeResponse:
    return RelationshipEdgeResponse(
        left_id=edge.left_id,
        right_id=edge.right_id,
        decision=edge.decision,
        reasons=list(edge.reasons),
        decision_source=edge.decision_source,
        matcher_recommendation=edge.matcher_recommendation,
    )


def _summary(read: IncidentRead) -> IncidentSummaryResponse:
    incident = read.incident
    return IncidentSummaryResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        category_summary=list(incident.category_summary),
        priority=_priority(read),
        confirmed_report_count=incident.report_count,
        pending_candidate_count=len(set(incident.review_candidate_ids)),
        centroid=GeoPointResponse(
            latitude=incident.centroid_latitude,
            longitude=incident.centroid_longitude,
        ),
        radius_metres=incident.radius_metres,
        earliest_reported_at=incident.earliest_reported_at,
        latest_reported_at=incident.latest_reported_at,
        conflict_reasons=list(incident.conflict_reasons),
    )


@router.get(
    "",
    response_model=IncidentListResponse,
    operation_id="incidentsList",
    description=(
        "List derived incident snapshots. Incident IDs identify the current "
        "membership-derived snapshot "
        "and may change when confirmed membership changes."
    ),
)
def list_incidents(
    query_service: IncidentQueryService = Depends(get_incident_query_service),  # noqa: B008
    status: ClusteringStatus | None = Query(default=None),  # noqa: B008
    priority: PriorityLevel | None = Query(default=None),  # noqa: B008
    category: Category | None = Query(default=None),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> IncidentListResponse:
    page = query_service.list_incidents(
        IncidentListQuery(
            status=status,
            priority=priority,
            category=category,
            limit=limit,
            offset=offset,
        )
    )
    return IncidentListResponse(
        items=[_summary(item) for item in page.items],
        limit=page.limit,
        offset=page.offset,
        total=page.total,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    operation_id="incidentDetail",
    description=(
        "Read a derived incident snapshot. Incident IDs identify the current "
        "membership-derived snapshot "
        "and may change when confirmed membership changes."
    ),
)
def get_incident(
    incident_id: UUID,
    query_service: IncidentQueryService = Depends(get_incident_query_service),  # noqa: B008
) -> IncidentDetailResponse:
    read = query_service.get_incident(incident_id)
    if read is None:
        raise ApiError(
            code="incident_not_found",
            message="The requested incident snapshot was not found.",
            status_code=404,
            details={"incident_id": str(incident_id)},
        )
    incident = read.incident
    return IncidentDetailResponse(
        **_summary(read).model_dump(),
        complaint_ids=list(incident.complaint_ids),
        review_candidate_ids=list(incident.review_candidate_ids),
        confirmed_edges=[_edge_response(edge) for edge in incident.confirmed_edges],
        review_candidates=[
            ReviewCandidateResponse(**_edge_response(edge).model_dump())
            for edge in incident.review_candidates
        ],
    )
