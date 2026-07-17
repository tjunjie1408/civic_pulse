"""Complaint request and response contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from civicpulse.api.dto.common import ApiModel
from civicpulse.domain import Category
from civicpulse.photos import UPLOADS_PREFIX


class ComplaintCreateRequest(ApiModel):
    text: str = Field(min_length=3, max_length=2000)
    latitude: float = Field(ge=-90, le=90, description="Latitude in decimal degrees.")
    longitude: float = Field(ge=-180, le=180, description="Longitude in decimal degrees.")
    reported_at: datetime = Field(description="Timezone-aware report time, normalized to UTC.")
    category: Category | None = None
    photo_id: UUID | None = Field(
        default=None,
        description="Identifier returned by the photo upload endpoint.",
    )
    photo_path: str | None = None

    @field_validator("reported_at")
    @classmethod
    def normalize_reported_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reported_at must include a timezone")
        return value.astimezone(UTC)

    @field_validator("photo_path")
    @classmethod
    def reject_reserved_prefix(cls, value: str | None) -> str | None:
        if value is not None and len(value) > 255:
            raise ValueError("photo_path must be at most 255 characters")
        if value is not None and value.startswith(UPLOADS_PREFIX):
            raise ValueError("photo_path may not reference the server uploads namespace")
        return value

    @model_validator(mode="after")
    def reject_conflicting_photo_fields(self) -> ComplaintCreateRequest:
        if self.photo_id is not None and self.photo_path is not None:
            raise ValueError("provide photo_id or photo_path, not both")
        return self


class ComplaintResponse(ApiModel):
    complaint_id: UUID
    text: str
    category: Category
    latitude: float
    longitude: float
    reported_at: datetime
    photo_path: str | None = None
