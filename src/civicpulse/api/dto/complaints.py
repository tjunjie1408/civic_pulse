"""Complaint request and response contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import Field, field_validator

from civicpulse.api.dto.common import ApiModel
from civicpulse.domain import Category


class ComplaintCreateRequest(ApiModel):
    text: str = Field(min_length=3, max_length=2000)
    latitude: float = Field(ge=-90, le=90, description="Latitude in decimal degrees.")
    longitude: float = Field(ge=-180, le=180, description="Longitude in decimal degrees.")
    reported_at: datetime = Field(description="Timezone-aware report time, normalized to UTC.")
    category: Category | None = None
    photo_path: str | None = None

    @field_validator("reported_at")
    @classmethod
    def normalize_reported_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reported_at must include a timezone")
        return value.astimezone(UTC)


class ComplaintResponse(ApiModel):
    complaint_id: UUID
    text: str
    category: Category
    latitude: float
    longitude: float
    reported_at: datetime
    photo_path: str | None = None
