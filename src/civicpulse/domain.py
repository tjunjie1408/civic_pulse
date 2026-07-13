"""Strict domain contracts for CivicPulse-lite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Similarity = Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]


class Category(StrEnum):
    """Supported complaint categories; OTHER requires human review."""

    POTHOLE = "pothole"
    BLOCKED_DRAIN = "blocked_drain"
    FLOODING = "flooding"
    RUBBISH = "rubbish"
    STREET_LIGHT = "street_light"
    OTHER = "other"


class PriorityLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REVIEW_REQUIRED = "review_required"


class PriorityStatus(StrEnum):
    SCORED = "scored"
    REVIEW_REQUIRED = "review_required"


class PhotoStatus(StrEnum):
    LIKELY_CONSISTENT = "likely_consistent"
    UNCLEAR = "unclear"
    LIKELY_INCONSISTENT = "likely_inconsistent"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class MatchState(StrEnum):
    AUTO_MATCH = "auto_match"
    NO_MATCH = "no_match"
    REVIEW_REQUIRED = "review_required"


class RelationshipDecisionSource(StrEnum):
    AUTOMATED = "automated"
    OFFICER_REVIEW = "officer_review"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ClusteringStatus(StrEnum):
    CONFIRMED = "confirmed"
    ISOLATED = "isolated"
    CONFLICT = "conflict"


class LocationEntityKind(StrEnum):
    BLOCK = "block"
    UNIT = "unit"
    STREET = "street"
    LANDMARK = "landmark"


class LocationCompatibility(StrEnum):
    COMPATIBLE = "compatible"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ComplaintInput(StrictModel):
    text: str = Field(min_length=3, max_length=2000)
    latitude: Latitude
    longitude: Longitude
    reported_at: datetime
    category: Category | None = None
    photo_path: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("text must contain at least 3 non-whitespace characters")
        return stripped

    @field_validator("reported_at")
    @classmethod
    def validate_reported_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reported_at must include a timezone")
        now = datetime.now(timezone.utc)
        if value.astimezone(timezone.utc) > now.replace(microsecond=0) + timedelta(minutes=5):
            raise ValueError("reported_at cannot be more than five minutes in the future")
        return value


class Complaint(ComplaintInput):
    id: UUID = Field(default_factory=uuid4)
    normalized_text: str = Field(min_length=3, max_length=2000)
    category: Category | None = Category.OTHER
    matched_terms: tuple[str, ...] = ()


class LocationEntity(StrictModel):
    kind: LocationEntityKind
    value: str = Field(min_length=1, max_length=160)
    raw: str = Field(min_length=1, max_length=200)


class LocationComparison(StrictModel):
    compatibility: LocationCompatibility
    first_entities: tuple[LocationEntity, ...]
    second_entities: tuple[LocationEntity, ...]
    reasons: tuple[str, ...] = Field(min_length=1)


class MatchDecision(StrictModel):
    decision: MatchState
    auto_match: bool
    review_required: bool
    category_compatible: bool
    location_compatibility: LocationCompatibility
    first_location_entities: tuple[LocationEntity, ...]
    second_location_entities: tuple[LocationEntity, ...]
    distance_metres: float = Field(ge=0, allow_inf_nan=False)
    time_gap_seconds: float = Field(ge=0, allow_inf_nan=False)
    semantic_similarity: Similarity
    reasons: tuple[str, ...] = Field(min_length=1)
    decision_source: RelationshipDecisionSource = RelationshipDecisionSource.AUTOMATED
    matcher_recommendation: MatchState | None = None


class RelationshipEdge(StrictModel):
    left_id: UUID
    right_id: UUID
    decision: MatchState
    reasons: tuple[str, ...] = Field(min_length=1)
    decision_source: RelationshipDecisionSource = RelationshipDecisionSource.AUTOMATED
    matcher_recommendation: MatchState | None = None


class Incident(StrictModel):
    incident_id: UUID
    complaint_ids: tuple[UUID, ...] = Field(min_length=1)
    report_count: int = Field(ge=1)
    confirmed_edges: tuple[RelationshipEdge, ...]
    review_candidate_ids: tuple[UUID, ...] = ()
    review_candidates: tuple[RelationshipEdge, ...] = ()
    centroid_latitude: Latitude
    centroid_longitude: Longitude
    radius_metres: float = Field(ge=0, allow_inf_nan=False)
    earliest_reported_at: datetime
    latest_reported_at: datetime
    category_summary: tuple[Category, ...] = Field(min_length=1)
    status: ClusteringStatus
    conflict_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_review_candidate_index(self) -> "Incident":
        if self.review_candidates:
            member_ids = set(self.complaint_ids)
            derived = {
                edge.right_id if edge.left_id in member_ids else edge.left_id
                for edge in self.review_candidates
                if edge.left_id in member_ids or edge.right_id in member_ids
            }
            if tuple(sorted(derived, key=str)) != tuple(sorted(self.review_candidate_ids, key=str)):
                raise ValueError("review_candidate_ids must be derived from review_candidates")
        return self

    @property
    def id(self) -> UUID:
        """Backward-compatible alias for the stable incident identifier."""
        return self.incident_id

    @property
    def member_ids(self) -> tuple[UUID, ...]:
        """Backward-compatible alias for complaint membership."""
        return self.complaint_ids

    @property
    def category(self) -> Category:
        """Return the deterministic primary category for legacy callers."""
        return self.category_summary[0]

    @property
    def first_reported_at(self) -> datetime:
        return self.earliest_reported_at

    @property
    def last_reported_at(self) -> datetime:
        return self.latest_reported_at

    @property
    def reasons(self) -> tuple[str, ...]:
        return self.conflict_reasons or (f"clustering status: {self.status.value}",)


class SensitiveLocation(StrictModel):
    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    latitude: Latitude
    longitude: Longitude


class PrioritySignal(StrictModel):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    normalized_value: float | None = Field(default=None, allow_inf_nan=False)
    triggered: bool
    reasons: tuple[str, ...] = ()


class PriorityAssessment(StrictModel):
    level: PriorityLevel
    status: PriorityStatus
    points: int = Field(ge=0)
    confirmed_report_count: int = Field(ge=0)
    pending_candidate_count: int = Field(ge=0)
    triggered_rules: tuple[str, ...] = ()
    signals: tuple[PrioritySignal, ...] = Field(min_length=1)
    reasons: tuple[str, ...] = Field(min_length=1)
    policy_version: str = Field(min_length=1)


class ReviewRecord(StrictModel):
    review_id: UUID
    left_id: UUID
    right_id: UUID
    matcher_recommendation: MatchState
    matcher_reasons: tuple[str, ...] = Field(min_length=1)
    status: ReviewStatus
    created_at: datetime
    resolved_at: datetime | None = None
    reviewed_by: str | None = None
    review_note: str | None = None
    final_relationship_state: MatchState | None = None
    decision_source: RelationshipDecisionSource | None = None
    graph_version_at_creation: str = Field(min_length=1)
    version: int = Field(ge=1)


class ReviewResolution(StrictModel):
    review_id: UUID
    previous_status: ReviewStatus
    final_status: ReviewStatus
    final_relationship_state: MatchState
    affected_complaint_ids: tuple[UUID, ...] = Field(min_length=1)
    previous_incident_ids: tuple[UUID, ...]
    new_incident_ids: tuple[UUID, ...]
    conflict_status: ClusteringStatus | None = None
    resulting_priorities: tuple[PriorityAssessment, ...]
    reviewer_id: str = Field(min_length=1)
    note: str | None = None


class PhotoAssessment(StrictModel):
    status: PhotoStatus
    observed_category: Category
    observation: str = Field(max_length=240)
    officer_review_required: bool = True
    model: str | None = None


class SubmissionResult(StrictModel):
    complaint: Complaint
    incident: Incident
    priority: PriorityAssessment
    created: bool
