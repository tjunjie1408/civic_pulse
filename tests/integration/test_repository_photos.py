from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from civicpulse.photos import StoredPhoto
from civicpulse.repository import SQLiteRepository

NOW = datetime(2026, 7, 17, 8, tzinfo=UTC)
PHOTO_ID = UUID("30000000-0000-0000-0000-000000000001")


def make_repository(tmp_path: Path) -> SQLiteRepository:
    repository = SQLiteRepository(tmp_path / "test.db")
    repository.initialize()
    return repository


def stored_photo() -> StoredPhoto:
    return StoredPhoto(
        photo_id=PHOTO_ID,
        media_type="image/jpeg",
        byte_size=2048,
        stored_name=f"{PHOTO_ID}.jpg",
    )


def test_add_and_get_photo_roundtrip(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.add_photo(stored_photo(), created_at=NOW)
    record = repository.get_photo(PHOTO_ID)
    assert record is not None
    assert record.media_type == "image/jpeg"
    assert record.byte_size == 2048
    assert record.stored_name == f"{PHOTO_ID}.jpg"


def test_get_photo_returns_none_for_unknown_id(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    assert repository.get_photo(PHOTO_ID) is None


def test_purge_photos_clears_all_rows(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.add_photo(stored_photo(), created_at=NOW)
    assert repository.purge_photos() == 1
    assert repository.get_photo(PHOTO_ID) is None
    assert repository.purge_photos() == 0


def test_initialize_is_idempotent_with_photos_table(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.add_photo(stored_photo(), created_at=NOW)
    repository.initialize()
    assert repository.get_photo(PHOTO_ID) is not None
