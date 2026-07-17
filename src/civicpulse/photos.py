"""Server-owned photo evidence storage on the local filesystem."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

MAX_PHOTO_BYTES = 8 * 1024 * 1024
UPLOADS_PREFIX = "uploads/"

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png"}
_KNOWN_SUFFIXES = {".jpg", ".png", ".tmp"}


class UnsupportedPhotoType(ValueError):
    """The uploaded bytes are not a JPEG or PNG image."""

    code = "unsupported_photo_type"

    def __init__(self) -> None:
        super().__init__("Only JPEG and PNG photos are supported.")


class PhotoTooLarge(ValueError):
    """The uploaded bytes exceed the configured size cap."""

    code = "photo_too_large"

    def __init__(self) -> None:
        super().__init__("Photos must be 8 MB or smaller.")


class PhotoNotFound(LookupError):
    """The requested photo file is not present in the store."""

    code = "photo_not_found"

    def __init__(self) -> None:
        super().__init__("The requested photo was not found.")


def sniff_media_type(content: bytes) -> str | None:
    """Identify JPEG or PNG from magic bytes; client headers are never trusted."""
    if content.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    if content.startswith(_PNG_MAGIC):
        return "image/png"
    return None


@dataclass(frozen=True)
class StoredPhoto:
    photo_id: UUID
    media_type: str
    byte_size: int
    stored_name: str


def photo_path_for(photo: StoredPhoto) -> str:
    """Return the server-owned complaint photo_path for a stored photo."""
    return f"{UPLOADS_PREFIX}{photo.stored_name}"


def photo_url_for(photo_path: str | None) -> str | None:
    """Derive the public photo URL from a complaint photo_path.

    Legacy free-text paths (seed data, pre-storage submissions) yield None.
    """
    if photo_path is None or not photo_path.startswith(UPLOADS_PREFIX):
        return None

    stored_name = photo_path[len(UPLOADS_PREFIX) :]
    stem, _, extension = stored_name.partition(".")
    if extension not in _EXTENSIONS.values():
        return None

    try:
        photo_id = UUID(stem)
    except ValueError:
        return None
    return f"/api/v1/photos/{photo_id}"


class PhotoStore:
    """Own the uploads directory; filenames are server-generated UUIDs."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def save(self, content: bytes) -> StoredPhoto:
        if len(content) > MAX_PHOTO_BYTES:
            raise PhotoTooLarge

        media_type = sniff_media_type(content)
        if media_type is None:
            raise UnsupportedPhotoType

        photo_id = uuid.uuid4()
        stored_name = f"{photo_id}.{_EXTENSIONS[media_type]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = self.directory / f"{stored_name}.tmp"
        final_path = self.directory / stored_name
        temp_path.write_bytes(content)
        os.replace(temp_path, final_path)
        return StoredPhoto(
            photo_id=photo_id,
            media_type=media_type,
            byte_size=len(content),
            stored_name=stored_name,
        )

    def resolve(self, stored_name: str) -> Path:
        path = self.directory / stored_name
        if not path.is_file():
            raise PhotoNotFound
        return path

    def purge(self) -> int:
        """Delete stored photo files; used by the admin demo reset."""
        if not self.directory.is_dir():
            return 0

        removed = 0
        for path in self.directory.iterdir():
            if path.is_file() and path.suffix in _KNOWN_SUFFIXES:
                path.unlink()
                removed += 1
        return removed

    def health_check(self) -> None:
        """Raise when the uploads directory cannot be created or written."""
        self.directory.mkdir(parents=True, exist_ok=True)
        probe = self.directory / ".health-probe"
        probe.write_bytes(b"ok")
        probe.unlink()
