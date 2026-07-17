from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from civicpulse.api import create_app
from civicpulse.photos import PhotoStore
from civicpulse.repository import SQLiteRepository

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def make_client(tmp_path: Path) -> TestClient:
    repository = SQLiteRepository(tmp_path / "photos.db")
    repository.initialize()
    store = PhotoStore(tmp_path / "uploads")
    return TestClient(create_app(repository=repository, photo_store=store))


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


def test_fetch_unknown_photo_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/api/v1/photos/30000000-0000-0000-0000-000000000001")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "photo_not_found"


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
