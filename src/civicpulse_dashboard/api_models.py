"""UI-facing models derived from the frozen API v1 contract.

This module deliberately does not import the CivicPulse domain package. The
dashboard is a client of the HTTP API, not another application-service layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

type Category = Literal[
    "pothole",
    "blocked_drain",
    "flooding",
    "rubbish",
    "street_light",
    "other",
]
type ClusteringStatus = Literal["confirmed", "isolated", "conflict"]
type PriorityLevel = Literal["critical", "high", "medium", "low", "review_required"]
type HealthStatus = Literal["healthy", "degraded", "unavailable"]
type MatchState = Literal["auto_match", "no_match", "review_required"]
type LocationCompatibility = Literal["compatible", "conflicting", "unknown"]
type LocationEntityKind = Literal["block", "unit", "street", "landmark"]
type RelationshipDecisionSource = Literal["automated", "officer_review"]
type ReviewStatus = Literal["pending", "approved", "rejected"]
type JsonScalar = str | int | float | bool | None


class DashboardModel(BaseModel):
    """Strict immutable response model shared by the dashboard client."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeoPointResponse(DashboardModel):
    latitude: float
    longitude: float


class PriorityResponse(DashboardModel):
    level: PriorityLevel
    reasons: list[str]
    policy_version: str


class ComplaintResponse(DashboardModel):
    complaint_id: UUID
    text: str
    category: Category
    latitude: float
    longitude: float
    reported_at: datetime
    photo_path: str | None = None


class ComplaintCreateRequest(DashboardModel):
    text: str = Field(min_length=3, max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    reported_at: datetime
    category: Category | None = None
    photo_path: str | None = None

    @field_validator("reported_at")
    @classmethod
    def normalize_reported_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reported_at must include a timezone")
        return value.astimezone(UTC)


class LocationEntityResponse(DashboardModel):
    kind: LocationEntityKind
    value: str
    raw: str


class ReviewEvidenceResponse(DashboardModel):
    semantic_similarity: float
    geo_distance_metres: float
    time_difference_seconds: float
    category_compatibility: bool
    location_compatibility: LocationCompatibility
    first_location_entities: list[LocationEntityResponse]
    second_location_entities: list[LocationEntityResponse]


class ReviewSummaryResponse(DashboardModel):
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


class ReviewListResponse(DashboardModel):
    items: list[ReviewSummaryResponse]
    limit: int
    offset: int
    total: int


class ReviewDetailResponse(DashboardModel):
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


class RelationshipEdgeResponse(DashboardModel):
    left_id: UUID
    right_id: UUID
    decision: MatchState
    reasons: list[str]
    decision_source: RelationshipDecisionSource
    matcher_recommendation: MatchState | None


class ReviewCandidateResponse(RelationshipEdgeResponse):
    pass


class IncidentSummaryResponse(DashboardModel):
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


class IncidentListResponse(DashboardModel):
    items: list[IncidentSummaryResponse]
    limit: int
    offset: int
    total: int


class IncidentTransitionResponse(DashboardModel):
    previous_incident_snapshot_ids: list[UUID]
    current_incident_snapshot_ids: list[UUID]


class ComplaintSubmissionResponse(DashboardModel):
    complaint: ComplaintResponse
    created: bool
    replayed: bool
    relationship_decisions: list[RelationshipEdgeResponse]
    incident_transition: IncidentTransitionResponse
    incidents: list[IncidentSummaryResponse]
    priorities: list[PriorityResponse | None]


class ApiErrorBody(DashboardModel):
    code: str
    message: str
    details: dict[str, JsonScalar]
    request_id: str


class ApiErrorResponse(DashboardModel):
    error: ApiErrorBody


class HealthComponentResponse(DashboardModel):
    status: HealthStatus
    message: str
    recovery_command: str | None = None


class LiveResponse(DashboardModel):
    status: Literal["alive"] = "alive"


class HealthResponse(DashboardModel):
    status: HealthStatus
    core_ready: bool
    database: HealthComponentResponse
    policies: HealthComponentResponse
    embedding_model: HealthComponentResponse
    seed: HealthComponentResponse
    photo_provider: HealthComponentResponse
