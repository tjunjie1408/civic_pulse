"""Review DTOs; resolution remains delegated to the application service."""

from __future__ import annotations

from uuid import UUID

from civicpulse.api.dto.common import ApiModel
from civicpulse.domain import MatchState, ReviewStatus


class ReviewSummaryResponse(ApiModel):
    review_id: UUID
    left_complaint_id: UUID
    right_complaint_id: UUID
    matcher_recommendation: MatchState
    status: ReviewStatus
    created_at: str
    resolved_at: str | None
    reviewer_id: str | None
    note: str | None


class ReviewResolutionRequest(ApiModel):
    approve: bool
    reviewer_id: str
    note: str | None = None
