from pathlib import Path
from uuid import UUID

import pytest

from civicpulse.photos import (
    MAX_PHOTO_BYTES,
    PhotoNotFound,
    PhotoStore,
    PhotoTooLarge,
    UnsupportedPhotoType,
    photo_path_for,
    photo_url_for,
    sniff_media_type,
)

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def test_sniff_media_type_recognizes_only_jpeg_and_png() -> None:
    assert sniff_media_type(JPEG_BYTES) == "image/jpeg"
    assert sniff_media_type(PNG_BYTES) == "image/png"
    assert sniff_media_type(b"GIF89a" + b"\x00" * 16) is None
    assert sniff_media_type(b"") is None


def test_save_stores_jpeg_with_uuid_name(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "uploads")
    stored = store.save(JPEG_BYTES)
    assert stored.media_type == "image/jpeg"
    assert stored.byte_size == len(JPEG_BYTES)
    assert stored.stored_name == f"{stored.photo_id}.jpg"
    assert store.resolve(stored.stored_name).read_bytes() == JPEG_BYTES


def test_save_rejects_unsupported_content(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "uploads")
    with pytest.raises(UnsupportedPhotoType):
        store.save(b"GIF89a" + b"\x00" * 16)
    assert store.purge() == 0


def test_save_rejects_oversized_content(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "uploads")
    oversized = b"\xff\xd8\xff" + b"\x00" * MAX_PHOTO_BYTES
    with pytest.raises(PhotoTooLarge):
        store.save(oversized)


def test_resolve_missing_file_raises(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "uploads")
    with pytest.raises(PhotoNotFound):
        store.resolve("00000000-0000-0000-0000-000000000001.jpg")


def test_purge_removes_stored_files(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "uploads")
    store.save(JPEG_BYTES)
    store.save(PNG_BYTES)
    assert store.purge() == 2
    assert store.purge() == 0


def test_service_reset_purges_photos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import MagicMock

    from civicpulse.service import CivicPulseService

    del tmp_path
    service = CivicPulseService.__new__(CivicPulseService)
    service.repository = MagicMock()
    service.photo_store = MagicMock()
    monkeypatch.setattr(
        CivicPulseService, "_import_seed", lambda self, path: "seed-result", raising=True
    )

    result = service.reset_seed("data/seed_complaints.json")

    assert result == "seed-result"
    service.repository.purge_photos.assert_called_once()
    service.photo_store.purge.assert_called_once()


def test_health_check_creates_and_probes_directory(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "uploads")
    store.health_check()
    assert (tmp_path / "uploads").is_dir()


def test_photo_url_for_derives_url_only_for_server_paths(tmp_path: Path) -> None:
    store = PhotoStore(tmp_path / "uploads")
    stored = store.save(JPEG_BYTES)
    path = photo_path_for(stored)
    assert path == f"uploads/{stored.photo_id}.jpg"
    assert photo_url_for(path) == f"/api/v1/photos/{stored.photo_id}"
    assert photo_url_for("uploads/00000000-0000-0000-0000-000000000000.jpg") is None
    assert photo_url_for(None) is None
    assert photo_url_for("evidence.jpg") is None
    assert photo_url_for("uploads/not-a-uuid.jpg") is None
    assert photo_url_for("uploads/00000000-0000-0000-0000-000000000001.gif") is None
    assert isinstance(stored.photo_id, UUID)


@pytest.mark.parametrize(
    ("stored_name",),
    [
        ("../escape.jpg",),
        ("..\\escape.jpg",),
        ("/absolute.jpg",),
        (r"C:\\absolute.jpg",),
        ("nested/escape.jpg",),
        ("uploads/../escape.jpg",),
    ],
)
def test_resolve_rejects_traversal_and_absolute_names(
    tmp_path: Path, stored_name: str
) -> None:
    store = PhotoStore(tmp_path / "uploads")
    with pytest.raises(PhotoNotFound):
        store.resolve(stored_name)
