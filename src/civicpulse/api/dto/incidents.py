"""Incident summary/detail contracts that hide internal graph structures."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from civicpulse.api.dto.common import ApiModel, GeoPointResponse
from civicpulse.domain import (
    Category,
    ClusteringStatus,
    MatchState,
    PriorityLevel,
    RelationshipDecisionSource,
)


class PriorityResponse(ApiModel):
    level: PriorityLevel
    reasons: list[str]
    policy_version: str


class RelationshipEdgeResponse(ApiModel):
    left_id: UUID
    right_id: UUID
    decision: MatchState
    reasons: list[str]
    decision_source: RelationshipDecisionSource
    matcher_recommendation: MatchState | None


class ReviewCandidateResponse(RelationshipEdgeResponse):
    pass


class ComplaintSummaryResponse(ApiModel):
    complaint_id: UUID
    text: str
    category: Category
    latitude: float
    longitude: float
    reported_at: datetime
    photo_available: bool
    photo_url: str | None


class IncidentEvidencePreviewResponse(ApiModel):
    items: list[ComplaintSummaryResponse]
    total: int
    has_more: bool


class IncidentSummaryResponse(ApiModel):
    incident_id: UUID
    status: ClusteringStatus
    category_summary: list[Category]
    priority: PriorityResponse | None
    confirmed_report_count: int
    pending_candidate_count: int
    centroid: GeoPointResponse
    radius_metres: float
    earliest_reported_at: datetime
    latest_reported_at: datetime
    conflict_reasons: list[str]


class IncidentDetailResponse(IncidentSummaryResponse):
    complaint_ids: list[UUID]
    review_candidate_ids: list[UUID]
    confirmed_edges: list[RelationshipEdgeResponse]
    review_candidates: list[ReviewCandidateResponse]
    confirmed_reports: IncidentEvidencePreviewResponse


class IncidentListResponse(ApiModel):
    items: list[IncidentSummaryResponse]
    limit: int
    offset: int
    total: int
