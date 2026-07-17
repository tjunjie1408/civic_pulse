from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from civicpulse.api import create_app
from civicpulse.photos import MAX_PHOTO_BYTES, PhotoStore, StoredPhoto
from civicpulse.repository import SQLiteRepository
from tests.contract.test_mutation_api import REQUEST, FakeMutationService

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class FailingPhotoRepository(SQLiteRepository):
    def add_photo(self, photo: StoredPhoto, created_at: datetime) -> None:
        del photo, created_at
        raise RuntimeError("database write failed")


def make_client(tmp_path: Path) -> TestClient:
    repository = SQLiteRepository(tmp_path / "photos.db")
    repository.initialize()
    store = PhotoStore(tmp_path / "uploads")
    return TestClient(create_app(repository=repository, photo_store=store))


def make_submission_client(
    tmp_path: Path,
) -> tuple[TestClient, FakeMutationService, PhotoStore, SQLiteRepository]:
    repository = SQLiteRepository(tmp_path / "photos.db")
    repository.initialize()
    store = PhotoStore(tmp_path / "uploads")
    service = FakeMutationService()
    client = TestClient(create_app(service=service, repository=repository, photo_store=store))
    return client, service, store, repository


def test_upload_and_fetch_roundtrip(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    upload = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.jpg", JPEG_BYTES, "image/jpeg")},
    )
    assert upload.status_code == 201
    body = upload.json()
    photo_id = UUID(body["photo_id"])
    assert body["media_type"] == "image/jpeg"
    assert body["byte_size"] == len(JPEG_BYTES)

    fetched = client.get(f"/api/v1/photos/{photo_id}")
    assert fetched.status_code == 200
    assert fetched.content == JPEG_BYTES
    assert fetched.headers["content-type"] == "image/jpeg"
    assert fetched.headers["x-content-type-options"] == "nosniff"
    assert "immutable" in fetched.headers["cache-control"]


def test_upload_trusts_magic_bytes_not_client_headers(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    upload = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.jpg", PNG_BYTES, "image/jpeg")},
    )
    assert upload.status_code == 201
    assert upload.json()["media_type"] == "image/png"


def test_upload_rejects_unsupported_content(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    upload = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.gif", b"GIF89a" + b"\x00" * 16, "image/gif")},
    )
    assert upload.status_code == 415
    assert upload.json()["error"]["code"] == "unsupported_photo_type"


def test_upload_rejects_oversized_content(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    oversized = b"\xff\xd8\xff" + b"\x00" * MAX_PHOTO_BYTES

    upload = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.jpg", oversized, "image/jpeg")},
    )

    assert upload.status_code == 413
    assert upload.json()["error"]["code"] == "photo_too_large"


def test_repository_failure_removes_saved_file_and_preserves_error_response(tmp_path: Path) -> None:
    repository = FailingPhotoRepository(tmp_path / "photos.db")
    repository.initialize()
    store = PhotoStore(tmp_path / "uploads")
    client = TestClient(create_app(repository=repository, photo_store=store))

    response = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.jpg", JPEG_BYTES, "image/jpeg")},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "database write failed" not in response.text
    assert list((tmp_path / "uploads").iterdir()) == []


def test_fetch_unknown_photo_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/api/v1/photos/30000000-0000-0000-0000-000000000001")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "photo_not_found"


def test_fetch_metadata_without_file_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    upload = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.jpg", JPEG_BYTES, "image/jpeg")},
    )
    photo_id = upload.json()["photo_id"]
    next((tmp_path / "uploads").iterdir()).unlink()

    response = client.get(f"/api/v1/photos/{photo_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "photo_not_found"


def test_successful_fetch_sets_inline_content_disposition(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    upload = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.jpg", JPEG_BYTES, "image/jpeg")},
    )
    photo_id = upload.json()["photo_id"]

    response = client.get(f"/api/v1/photos/{photo_id}")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == "inline"


def test_photo_routes_require_configured_store(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "no-store.db")
    repository.initialize()
    client = TestClient(create_app(repository=repository))
    upload = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.jpg", JPEG_BYTES, "image/jpeg")},
    )
    assert upload.status_code == 503
    assert upload.json()["error"]["code"] == "readiness_failure"


def test_complaint_with_photo_id_stores_server_owned_path(tmp_path: Path) -> None:
    client, service, _store, _repository = make_submission_client(tmp_path)
    upload = client.post(
        "/api/v1/photos",
        files={"file": ("evidence.jpg", JPEG_BYTES, "image/jpeg")},
    )
    photo_id = upload.json()["photo_id"]
    response = client.post(
        "/api/v1/complaints",
        json={**REQUEST, "photo_id": photo_id},
        headers={"Idempotency-Key": "photo-key-1"},
    )
    assert response.status_code == 201
    submitted_payload, _key = service.submissions[0]
    assert getattr(submitted_payload, "photo_path") == f"uploads/{photo_id}.jpg"


def test_complaint_with_unknown_photo_id_is_rejected(tmp_path: Path) -> None:
    client, service, _store, _repository = make_submission_client(tmp_path)
    response = client.post(
        "/api/v1/complaints",
        json={**REQUEST, "photo_id": "30000000-0000-0000-0000-000000000009"},
        headers={"Idempotency-Key": "photo-key-2"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_photo"
    assert service.submissions == []


def test_complaint_rejects_reserved_photo_path_prefix(tmp_path: Path) -> None:
    client, _service, _store, _repository = make_submission_client(tmp_path)
    response = client.post(
        "/api/v1/complaints",
        json={**REQUEST, "photo_path": "uploads/spoofed.jpg"},
        headers={"Idempotency-Key": "photo-key-3"},
    )
    assert response.status_code == 422


def test_complaint_rejects_photo_id_and_photo_path_together(tmp_path: Path) -> None:
    client, _service, _store, _repository = make_submission_client(tmp_path)
    response = client.post(
        "/api/v1/complaints",
        json={
            **REQUEST,
            "photo_id": "30000000-0000-0000-0000-000000000001",
            "photo_path": "note.jpg",
        },
        headers={"Idempotency-Key": "photo-key-4"},
    )
    assert response.status_code == 422
