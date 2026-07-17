"""Photo evidence upload and retrieval endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse

from civicpulse.api.dependencies import get_photo_store, get_repository
from civicpulse.api.dto.common import ApiErrorResponse
from civicpulse.api.dto.photos import PhotoUploadResponse
from civicpulse.api.errors import ApiError
from civicpulse.photos import (
    MAX_PHOTO_BYTES,
    PhotoNotFound,
    PhotoStore,
    PhotoTooLarge,
    UnsupportedPhotoType,
)
from civicpulse.repository import SQLiteRepository

router = APIRouter(prefix="/photos", tags=["photos"])

_PHOTO_HEADERS = {
    "Cache-Control": "private, max-age=31536000, immutable",
    "X-Content-Type-Options": "nosniff",
    "Content-Disposition": "inline",
}


@router.post(
    "",
    response_model=PhotoUploadResponse,
    status_code=201,
    operation_id="photosUpload",
    description=(
        "Upload JPEG or PNG photo evidence. The media type is detected from the file "
        "content; the server assigns the stored name."
    ),
    responses={
        413: {"model": ApiErrorResponse, "description": "Photo exceeds the size cap."},
        415: {"model": ApiErrorResponse, "description": "Unsupported photo content."},
        422: {"model": ApiErrorResponse, "description": "Request validation failed."},
    },
)
async def upload_photo(
    file: UploadFile,
    store: PhotoStore = Depends(get_photo_store),  # noqa: B008
    repository: SQLiteRepository = Depends(get_repository),  # noqa: B008
) -> PhotoUploadResponse:
    content = await file.read(MAX_PHOTO_BYTES + 1)
    try:
        stored = store.save(content)
    except UnsupportedPhotoType as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=415) from exc
    except PhotoTooLarge as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=413) from exc
    repository.add_photo(stored, created_at=datetime.now(UTC))
    return PhotoUploadResponse(
        photo_id=stored.photo_id,
        media_type=stored.media_type,
        byte_size=stored.byte_size,
    )


@router.get(
    "/{photo_id}",
    operation_id="photosGet",
    response_class=FileResponse,
    description="Serve stored photo evidence with its recorded media type.",
    responses={
        404: {"model": ApiErrorResponse, "description": "Photo not found."},
    },
)
def get_photo(
    photo_id: UUID,
    store: PhotoStore = Depends(get_photo_store),  # noqa: B008
    repository: SQLiteRepository = Depends(get_repository),  # noqa: B008
) -> FileResponse:
    record = repository.get_photo(photo_id)
    if record is None:
        raise ApiError(
            code="photo_not_found",
            message="The requested photo was not found.",
            status_code=404,
            details={"photo_id": str(photo_id)},
        )
    try:
        path = store.resolve(record.stored_name)
    except PhotoNotFound as exc:
        raise ApiError(
            code="photo_not_found",
            message="The requested photo was not found.",
            status_code=404,
            details={"photo_id": str(photo_id)},
        ) from exc
    return FileResponse(path, media_type=record.media_type, headers=_PHOTO_HEADERS)
