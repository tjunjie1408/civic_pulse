"""UI-facing models derived from the frozen API v1 contract.

This module deliberately does not import the CivicPulse domain package. The
dashboard is a client of the HTTP API, not another application-service layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
    confirmed_edges: list[dict[str, object]]
    review_candidates: list[dict[str, object]]


class IncidentListResponse(DashboardModel):
    items: list[IncidentSummaryResponse]
    limit: int
    offset: int
    total: int


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


class HealthResponse(DashboardModel):
    status: HealthStatus
    core_ready: bool
    database: HealthComponentResponse
    policies: HealthComponentResponse
    embedding_model: HealthComponentResponse
    seed: HealthComponentResponse
    photo_provider: HealthComponentResponse
