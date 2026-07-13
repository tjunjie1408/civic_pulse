"""Strict mutation request and response contracts."""

from __future__ import annotations

from uuid import UUID

from civicpulse.api.dto.common import ApiModel
from civicpulse.api.dto.complaints import ComplaintResponse
from civicpulse.api.dto.incidents import (
    IncidentSummaryResponse,
    PriorityResponse,
    RelationshipEdgeResponse,
)


class IncidentTransitionResponse(ApiModel):
    previous_incident_snapshot_ids: list[UUID]
    current_incident_snapshot_ids: list[UUID]


class ComplaintSubmissionResponse(ApiModel):
    complaint: ComplaintResponse
    created: bool
    replayed: bool
    relationship_decisions: list[RelationshipEdgeResponse]
    incident_transition: IncidentTransitionResponse
    incidents: list[IncidentSummaryResponse]
    priorities: list[PriorityResponse | None]


class SeedResetResponse(ApiModel):
    seed_version: str
    seed_checksum: str
    complaint_count: int
    incident_count: int
    review_counts: dict[str, int]
    priority_counts: dict[str, int]
