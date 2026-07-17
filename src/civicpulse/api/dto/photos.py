"""Photo upload contracts."""

from __future__ import annotations

from uuid import UUID

from civicpulse.api.dto.common import ApiModel


class PhotoUploadResponse(ApiModel):
    photo_id: UUID
    media_type: str
    byte_size: int
