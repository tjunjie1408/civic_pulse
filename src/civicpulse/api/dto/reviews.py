"""Strict review read and resolution contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from civicpulse.api.dto.common import ApiModel
from civicpulse.api.dto.complaints import ComplaintResponse
from civicpulse.api.dto.incidents import IncidentSummaryResponse, PriorityResponse
from civicpulse.domain import (
    ClusteringStatus,
    LocationCompatibility,
    LocationEntityKind,
    MatchState,
    RelationshipDecisionSource,
    ReviewStatus,
)


class LocationEntityResponse(ApiModel):
    kind: LocationEntityKind
    value: str
    raw: str


class ReviewEvidenceResponse(ApiModel):
    semantic_similarity: float
    geo_distance_metres: float
    time_difference_seconds: float
    category_compatibility: bool
    location_compatibility: LocationCompatibility
    first_location_entities: list[LocationEntityResponse]
    second_location_entities: list[LocationEntityResponse]


class ReviewSummaryResponse(ApiModel):
    review_id: UUID
    left_complaint_id: UUID
    right_complaint_id: UUID
    original_matcher_recommendation: MatchState
    matcher_reasons: list[str]
    status: ReviewStatus
    created_at: datetime
    resolved_at: datetime | None
    reviewer_id: str | None
    review_note: str | None
    final_relationship_state: MatchState | None
    decision_source: RelationshipDecisionSource | None
    graph_version: str


class ReviewListResponse(ApiModel):
    items: list[ReviewSummaryResponse]
    limit: int
    offset: int
    total: int


class ReviewDetailResponse(ApiModel):
    review_id: UUID
    status: ReviewStatus
    complaint_a: ComplaintResponse
    complaint_b: ComplaintResponse
    original_matcher_recommendation: MatchState
    matcher_reasons: list[str]
    matcher_evidence: ReviewEvidenceResponse | None
    created_at: datetime
    resolved_at: datetime | None
    reviewer_id: str | None
    review_note: str | None
    final_relationship_state: MatchState | None
    decision_source: RelationshipDecisionSource | None
    graph_version: str
    previous_incident_snapshot_ids: list[UUID]
    new_incident_snapshot_ids: list[UUID]


class ReviewResolutionRequest(ApiModel):
    reviewer_id: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("reviewer_id")
    @classmethod
    def validate_reviewer_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reviewer_id must not be blank")
        return stripped


class ReviewMutationResponse(ApiModel):
    review: ReviewDetailResponse
    final_relationship_state: MatchState
    affected_complaint_ids: list[UUID]
    previous_incident_snapshot_ids: list[UUID]
    new_incident_snapshot_ids: list[UUID]
    affected_incidents: list[IncidentSummaryResponse]
    resulting_priorities: list[PriorityResponse | None]
    conflict_status: ClusteringStatus | None
