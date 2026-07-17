# Photo Evidence Storage and Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store report photos server-side (files in `data/uploads/`, metadata in SQLite), serve them through `GET /api/v1/photos/{photo_id}`, and render them inside the incident detail page, replacing today's client-side-only photo preview.

**Architecture:** A new `PhotoStore` owns the uploads directory (UUID filenames, media type from sniffed magic bytes, never from client input). SQLite gains a `photos` metadata table. Two new endpoints (`POST /api/v1/photos` multipart upload, `GET /api/v1/photos/{photo_id}` binary fetch) join the v1 API; `ComplaintCreateRequest` gains `photo_id` and the server derives the stored `photo_path` itself; incident-detail evidence rows gain `photo_url`. This is an explicit, reviewed OpenAPI snapshot update, not a silent contract break. The Vue frontend uploads the photo on selection through a new hexagonal port/adapter pair and renders `photo_url` thumbnails in `IncidentDetailPage.vue`. The Streamlit dashboard keeps working unchanged because `photo_path` stays accepted (with a reserved-prefix guard).

**Tech Stack:** FastAPI + `python-multipart` (new dependency, one-time network install), SQLite (metadata only, no BLOBs), pytest (unit/integration/contract), openapi-typescript regeneration, Vue 3 + TypeScript with the existing ports-and-adapters layout, Vitest.

## Why files on disk, not BLOBs

SQLite BLOB storage only outperforms the filesystem for objects under roughly 100 KB; report photos are up to 8 MB. This repo also atomically replaces the database on demo reset, so multi-megabyte blobs would bloat that path. Metadata (id, stored name, sniffed media type, byte size, created time) lives in SQLite for referential checks and listing; bytes live in `data/uploads/`.

## Global Constraints

- **Contract change is explicit.** `tests/contracts/openapi-v1.json` is regenerated only via `uv run --offline python -m scripts.update_openapi_snapshot` in Task 7, after all backend endpoints exist. `AppSettings.version` bumps `1.0.0` → `1.1.0`. No other step touches the snapshot.
- **Backward compatibility with the Streamlit dashboard.** `ComplaintCreateRequest.photo_path` remains accepted (the Streamlit client sends it, defaulting to null). New rule: values starting with `uploads/` are rejected (reserved server namespace) and supplying both `photo_id` and `photo_path` is rejected.
- **Server owns all paths and media types.** Stored filename is `{uuid4}.{jpg|png}`; media type comes only from magic-byte sniffing (`\xff\xd8\xff` JPEG, `\x89PNG\r\n\x1a\n` PNG); responses carry `X-Content-Type-Options: nosniff` and `Content-Disposition: inline`. Client-supplied filenames, extensions, and Content-Type headers are never trusted.
- **Size cap 8 MB** (`MAX_PHOTO_BYTES = 8 * 1024 * 1024`), matching the existing frontend `photo.ts` constant.
- **Reset purges photos.** `service.reset_seed` clears the `photos` table and deletes files in the uploads directory after a successful seed import. Orphan uploads (photo uploaded, complaint never submitted) are acceptable between resets.
- **Priority policy is untouched.** It already counts `photo_path is not None` on confirmed complaints; server-derived paths keep feeding it.
- **New dependency:** `python-multipart` (FastAPI multipart parsing). `uv add python-multipart` needs network once; everything after stays offline.
- **Frontend decoders are exact-key.** `decode-incident-detail.ts` rejects unknown AND missing keys (`hasExactKeys`), so backend field additions and frontend decoder updates must land before the two are run against each other; in this monorepo that means backend tasks first, frontend tasks after the snapshot regen, same branch.
- **Quality gates at every commit:** `uv run --offline python -m pytest -q` and `uv run --offline pyright src scripts` for backend tasks; `pnpm run check` (api:check + lint + test + build) inside `frontend/` for frontend tasks. Ruff line length 100, pyright strict.
- **Copy rules:** plain sentences, no em-dash characters in any user-visible string.

## File Structure

```
Backend
├── pyproject.toml                                  Modify: add python-multipart
├── src/civicpulse/photos.py                        Create: PhotoStore, sniffing, URL derivation, errors
├── src/civicpulse/repository.py                    Modify: photos table + add/get/purge methods
├── src/civicpulse/service.py                       Modify: photo_store param, reset purge
├── src/civicpulse/runtime.py                       Modify: uploads_path setting, PhotoStore wiring
├── src/civicpulse/api/app.py                       Modify: photo_store injection, photos router, v1.1.0
├── src/civicpulse/api/dependencies.py              Modify: get_photo_store, get_repository
├── src/civicpulse/api/dto/photos.py                Create: PhotoUploadResponse
├── src/civicpulse/api/dto/complaints.py            Modify: photo_id + reserved-prefix guard
├── src/civicpulse/api/dto/incidents.py             Modify: ComplaintSummaryResponse.photo_url
├── src/civicpulse/api/routes/photos.py             Create: upload + fetch endpoints
├── src/civicpulse/api/routes/mutations.py          Modify: photo_id resolution
├── src/civicpulse/api/routes/incidents.py          Modify: photo_url projection
├── tests/unit/test_photo_store.py                  Create
├── tests/integration/test_repository_photos.py     Create
├── tests/contract/test_photo_api.py                Create
└── tests/contracts/openapi-v1.json                 Regenerated in Task 7 only

Frontend (all under frontend/src)
├── features/submissions/application/photo-upload-port.ts    Create: port + result types
├── features/submissions/application/upload-photo.ts         Create: application service
├── features/submissions/adapters/http/photo-http-adapter.ts Create: multipart adapter + decode
├── features/submissions/domain/complaint.ts                 Modify: request carries photoId
├── features/submissions/adapters/http/complaint-http-adapter.ts  Modify: send photo_id
├── features/submissions/ui/SubmitPage.vue                   Modify: upload-on-select flow
├── features/incidents/domain/incident.ts                    Modify: photoUrl on complaint summary
├── features/incidents/adapters/http/decode-incident-detail.ts    Modify: decode photo_url
├── features/incidents/testing/incident-fixtures.ts          Modify: add photo_url fields
├── features/incidents/ui/IncidentDetailPage.vue              Modify: render photo thumbnails
├── features/incidents/adapters/http/generated/openapi.d.ts  Regenerated via pnpm api:generate
└── composition/create-app-services.ts                        Modify: wire UploadPhoto
```

---

### Task 1: PhotoStore module (file storage, sniffing, URL derivation)

**Files:**
- Modify: `pyproject.toml` (dependencies list)
- Create: `src/civicpulse/photos.py`
- Test: `tests/unit/test_photo_store.py`

**Interfaces:**
- Consumes: nothing app-specific (pure stdlib + filesystem)
- Produces: `MAX_PHOTO_BYTES: int`; `sniff_media_type(content: bytes) -> str | None`; `StoredPhoto` (frozen dataclass: `photo_id: UUID`, `media_type: str`, `byte_size: int`, `stored_name: str`); `photo_path_for(photo: StoredPhoto) -> str` (returns `uploads/{stored_name}`); `photo_url_for(photo_path: str | None) -> str | None` (returns `/api/v1/photos/{uuid}` or None for legacy paths); `UPLOADS_PREFIX = "uploads/"`; `PhotoStore(directory)` with `save(content: bytes) -> StoredPhoto`, `resolve(stored_name: str) -> Path`, `purge() -> int`, `health_check() -> None`; errors `UnsupportedPhotoType` (`.code = "unsupported_photo_type"`), `PhotoTooLarge` (`.code = "photo_too_large"`), `PhotoNotFound` (`.code = "photo_not_found"`).

- [ ] **Step 1: Add the dependency**

Run: `uv add python-multipart` (needs network once).
Expected: `pyproject.toml` dependencies gain `"python-multipart>=0.0.20"` (version as resolved) and `uv.lock` updates. Then confirm offline sync works: `uv sync --offline` → succeeds.

- [ ] **Step 2: Write the failing test `tests/unit/test_photo_store.py`**

```python
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
    assert photo_url_for(None) is None
    assert photo_url_for("evidence.jpg") is None
    assert photo_url_for("uploads/not-a-uuid.jpg") is None
    assert photo_url_for("uploads/00000000-0000-0000-0000-000000000001.gif") is None
    assert isinstance(stored.photo_id, UUID)
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --offline python -m pytest tests/unit/test_photo_store.py -q`
Expected: FAIL, `ModuleNotFoundError: civicpulse.photos`.

- [ ] **Step 4: Write `src/civicpulse/photos.py`**

```python
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
    """Server-owned complaint photo_path value for a stored photo."""
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
    """Owns the uploads directory; filenames are server-generated UUIDs."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def save(self, content: bytes) -> StoredPhoto:
        media_type = sniff_media_type(content)
        if media_type is None:
            raise UnsupportedPhotoType
        if len(content) > MAX_PHOTO_BYTES:
            raise PhotoTooLarge
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
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run --offline python -m pytest tests/unit/test_photo_store.py -q`
Expected: 8 passed.
Run: `uv run --offline pyright src scripts` → 0 errors.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml uv.lock src/civicpulse/photos.py tests/unit/test_photo_store.py
git commit -m "feat(photos): filesystem photo store with sniffed media types"
```

---

### Task 2: SQLite photo metadata (table + repository methods)

**Files:**
- Modify: `src/civicpulse/repository.py`
- Test: `tests/integration/test_repository_photos.py`

**Interfaces:**
- Consumes: `StoredPhoto` from `civicpulse.photos`
- Produces: `photos` table created in `SQLiteRepository.initialize()`; `add_photo(photo: StoredPhoto, created_at: datetime) -> None`; `get_photo(photo_id: UUID) -> StoredPhoto | None`; `purge_photos() -> int`. Schema version stays 1; the table is additive via `CREATE TABLE IF NOT EXISTS`, matching the repo's existing additive-migration pattern (`ALTER TABLE` guards).

- [ ] **Step 1: Write the failing test `tests/integration/test_repository_photos.py`**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --offline python -m pytest tests/integration/test_repository_photos.py -q`
Expected: FAIL, `add_photo` does not exist.

- [ ] **Step 3: Add the table to `initialize()`**

In `src/civicpulse/repository.py`, inside the `executescript` block of `initialize()` (after the `reviews` table definition, before the closing `"""`), add:

```sql
CREATE TABLE IF NOT EXISTS photos (
    photo_id TEXT PRIMARY KEY,
    stored_name TEXT NOT NULL UNIQUE,
    media_type TEXT NOT NULL CHECK(media_type IN ('image/jpeg','image/png')),
    byte_size INTEGER NOT NULL CHECK(byte_size > 0),
    created_at TEXT NOT NULL
);
```

Add the import at the top of the file with the existing domain imports:

```python
from civicpulse.photos import StoredPhoto
```

- [ ] **Step 4: Add the repository methods**

Add to `SQLiteRepository` (near `add_complaint`, following its transaction and error style):

```python
def add_photo(self, photo: StoredPhoto, created_at: datetime) -> None:
    with self.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                "INSERT INTO photos(photo_id,stored_name,media_type,byte_size,created_at) "
                "VALUES(?,?,?,?,?)",
                (
                    str(photo.photo_id),
                    photo.stored_name,
                    photo.media_type,
                    photo.byte_size,
                    created_at.isoformat(),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

def get_photo(self, photo_id: UUID) -> StoredPhoto | None:
    with self.connect() as connection:
        row = connection.execute(
            "SELECT photo_id,stored_name,media_type,byte_size FROM photos WHERE photo_id=?",
            (str(photo_id),),
        ).fetchone()
    if row is None:
        return None
    return StoredPhoto(
        photo_id=UUID(row["photo_id"]),
        media_type=row["media_type"],
        byte_size=row["byte_size"],
        stored_name=row["stored_name"],
    )

def purge_photos(self) -> int:
    with self.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            cursor = connection.execute("DELETE FROM photos")
            connection.commit()
            return cursor.rowcount
        except Exception:
            connection.rollback()
            raise
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run --offline python -m pytest tests/integration/test_repository_photos.py -q`
Expected: 4 passed.
Run: `uv run --offline python -m pytest -q` → full suite still green (existing DBs gain the table via `CREATE TABLE IF NOT EXISTS`).
Run: `uv run --offline pyright src scripts` → 0 errors.

- [ ] **Step 6: Commit**

```powershell
git add src/civicpulse/repository.py tests/integration/test_repository_photos.py
git commit -m "feat(photos): SQLite photo metadata table and repository methods"
```

---

### Task 3: Photo API endpoints (upload + fetch)

**Files:**
- Create: `src/civicpulse/api/dto/photos.py`
- Create: `src/civicpulse/api/routes/photos.py`
- Modify: `src/civicpulse/api/dependencies.py`
- Modify: `src/civicpulse/api/app.py`
- Test: `tests/contract/test_photo_api.py`

**Interfaces:**
- Consumes: `PhotoStore`, repository photo methods (Tasks 1 and 2), existing `ApiError` and `create_app` injection pattern
- Produces: `POST /api/v1/photos` (multipart field `file`) → 201 `PhotoUploadResponse { photo_id: UUID, media_type: str, byte_size: int }`, 413 `photo_too_large`, 415 `unsupported_photo_type`; `GET /api/v1/photos/{photo_id}` → binary `FileResponse` with stored media type, `Cache-Control: private, max-age=31536000, immutable`, `X-Content-Type-Options: nosniff`, `Content-Disposition: inline`, 404 `photo_not_found`; dependencies `get_photo_store(request)` and `get_repository(request)` (503 `readiness_failure` when unset); `create_app(..., photo_store: PhotoStore | None = None)` storing `app.state.photo_store` and including the photos router.

- [ ] **Step 1: Write the failing test `tests/contract/test_photo_api.py`**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --offline python -m pytest tests/contract/test_photo_api.py -q`
Expected: FAIL (`create_app` has no `photo_store` parameter; routes missing).

- [ ] **Step 3: Write `src/civicpulse/api/dto/photos.py`**

```python
"""Photo upload contracts."""

from __future__ import annotations

from uuid import UUID

from civicpulse.api.dto.common import ApiModel


class PhotoUploadResponse(ApiModel):
    photo_id: UUID
    media_type: str
    byte_size: int
```

- [ ] **Step 4: Add dependencies in `src/civicpulse/api/dependencies.py`**

Add imports:

```python
from civicpulse.photos import PhotoStore
from civicpulse.repository import SQLiteRepository
```

Add functions (same style as `get_service`):

```python
def get_photo_store(request: Request) -> PhotoStore:
    store = getattr(request.app.state, "photo_store", None)
    if store is None:
        raise ApiError(
            code="readiness_failure",
            message="Photo storage is not configured.",
            status_code=503,
        )
    return cast(PhotoStore, store)


def get_repository(request: Request) -> SQLiteRepository:
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise ApiError(
            code="readiness_failure",
            message="Application services are not configured.",
            status_code=503,
        )
    return cast(SQLiteRepository, repository)
```

- [ ] **Step 5: Write `src/civicpulse/api/routes/photos.py`**

```python
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
```

- [ ] **Step 6: Wire the router and store into `src/civicpulse/api/app.py`**

Add imports:

```python
from civicpulse.api.routes.photos import router as photos_router
from civicpulse.photos import PhotoStore
```

Extend `create_app`'s signature with `photo_store: PhotoStore | None = None` (after `incident_query_service`), then inside the body add `app.state.photo_store = photo_store` next to the other state assignments and `app.include_router(photos_router, prefix=resolved.api_prefix)` after the reviews router.

- [ ] **Step 7: Run to verify pass**

Run: `uv run --offline python -m pytest tests/contract/test_photo_api.py -q`
Expected: 5 passed.
Note: `tests/contract/test_openapi_freeze.py` now FAILS because the generated schema gained the photos routes. That is expected and stays red until Task 7 regenerates the snapshot; run the rest of the suite with `uv run --offline python -m pytest -q --deselect tests/contract/test_openapi_freeze.py` for interim checks.
Run: `uv run --offline pyright src scripts` → 0 errors.

- [ ] **Step 8: Commit**

```powershell
git add src/civicpulse/api tests/contract/test_photo_api.py
git commit -m "feat(photos): upload and fetch endpoints with sniffed media types"
```

---

### Task 4: Complaint submission accepts `photo_id`

**Files:**
- Modify: `src/civicpulse/api/dto/complaints.py`
- Modify: `src/civicpulse/api/routes/mutations.py`
- Test: extend `tests/contract/test_photo_api.py`

**Interfaces:**
- Consumes: repository `get_photo`, `photo_path_for`, `UPLOADS_PREFIX` (Tasks 1 and 2)
- Produces: `ComplaintCreateRequest` gains `photo_id: UUID | None = None`; `photo_path` stays accepted (Streamlit compatibility) but may not start with `uploads/` and may not be combined with `photo_id`; the complaints route resolves `photo_id` → server-owned `photo_path` before calling the service; unknown `photo_id` → 422 `unknown_photo`. `ComplaintResponse` is unchanged.

- [ ] **Step 1: Write the failing tests (append to `tests/contract/test_photo_api.py`)**

The mutations route needs a service; reuse the `FakeMutationService` from `tests/contract/test_mutation_api.py` by importing it.

```python
from tests.contract.test_mutation_api import REQUEST, FakeMutationService


def make_submission_client(tmp_path: Path) -> tuple[TestClient, FakeMutationService, PhotoStore, SQLiteRepository]:
    repository = SQLiteRepository(tmp_path / "photos.db")
    repository.initialize()
    store = PhotoStore(tmp_path / "uploads")
    service = FakeMutationService()
    client = TestClient(create_app(service=service, repository=repository, photo_store=store))
    return client, service, store, repository


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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --offline python -m pytest tests/contract/test_photo_api.py -q`
Expected: the 4 new tests FAIL (`photo_id` not a known field).

- [ ] **Step 3: Update `ComplaintCreateRequest` in `src/civicpulse/api/dto/complaints.py`**

Replace the model with (imports gain `model_validator` from pydantic; keep everything else in the file unchanged):

```python
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
    photo_path: str | None = Field(
        default=None,
        max_length=255,
        description="Legacy free-text photo reference; server-managed uploads use photo_id.",
    )

    @field_validator("reported_at")
    @classmethod
    def normalize_reported_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reported_at must include a timezone")
        return value.astimezone(UTC)

    @field_validator("photo_path")
    @classmethod
    def reject_reserved_prefix(cls, value: str | None) -> str | None:
        if value is not None and value.startswith("uploads/"):
            raise ValueError("photo_path may not reference the server uploads namespace")
        return value

    @model_validator(mode="after")
    def reject_conflicting_photo_fields(self) -> ComplaintCreateRequest:
        if self.photo_id is not None and self.photo_path is not None:
            raise ValueError("provide photo_id or photo_path, not both")
        return self
```

- [ ] **Step 4: Resolve `photo_id` in `src/civicpulse/api/routes/mutations.py`**

Add imports:

```python
from civicpulse.api.dependencies import get_repository
from civicpulse.photos import photo_path_for
from civicpulse.repository import SQLiteRepository
```

In `submit_complaint`, add the repository dependency to the signature:

```python
repository: SQLiteRepository = Depends(get_repository),  # noqa: B008
```

Replace the `payload = ComplaintInput.model_validate(request.model_dump())` block with explicit construction (the request now carries `photo_id`, which `ComplaintInput` must never see):

```python
    resolved_photo_path = request.photo_path
    if request.photo_id is not None:
        record = repository.get_photo(request.photo_id)
        if record is None:
            raise ApiError(
                code="unknown_photo",
                message="The referenced photo upload was not found.",
                status_code=422,
                details={"photo_id": str(request.photo_id)},
            )
        resolved_photo_path = photo_path_for(record)
    try:
        payload = ComplaintInput(
            text=request.text,
            latitude=request.latitude,
            longitude=request.longitude,
            reported_at=request.reported_at,
            category=request.category,
            photo_path=resolved_photo_path,
        )
    except ValidationError as exc:
        raise ApiError(
            code="validation_error",
            message="Request validation failed.",
            status_code=422,
            details={"error_count": len(exc.errors())},
        ) from exc
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run --offline python -m pytest tests/contract/test_photo_api.py tests/contract/test_mutation_api.py tests/contract/test_dashboard_submission.py -q`
Expected: all pass (the Streamlit gateway tests confirm `photo_path`-only submissions still work).
Run: `uv run --offline python -m pytest -q --deselect tests/contract/test_openapi_freeze.py` → green.
Run: `uv run --offline pyright src scripts` → 0 errors.

- [ ] **Step 6: Commit**

```powershell
git add src/civicpulse/api tests/contract/test_photo_api.py
git commit -m "feat(photos): complaint submission references uploads by photo_id"
```

---

### Task 5: Incident detail exposes `photo_url`

**Files:**
- Modify: `src/civicpulse/api/dto/incidents.py`
- Modify: `src/civicpulse/api/routes/incidents.py`
- Test: extend `tests/contract/test_incident_read_api.py`

**Interfaces:**
- Consumes: `photo_url_for` (Task 1)
- Produces: `ComplaintSummaryResponse` gains `photo_url: str | None`; the incident detail route fills it with `photo_url_for(complaint.photo_path)`. Legacy free-text photo paths keep `photo_available: true` with `photo_url: null`.

- [ ] **Step 1: Write the failing test**

Open `tests/contract/test_incident_read_api.py`, find the existing detail test that asserts on `confirmed_reports` items (it drives the fake query service's evidence complaints). Add one focused test following that file's existing fixture pattern; the essential assertions are:

```python
def test_incident_detail_maps_photo_url_from_server_paths() -> None:
    # Arrange two evidence complaints through this file's existing fake
    # query-service fixtures: one with
    #   photo_path="uploads/30000000-0000-0000-0000-000000000001.jpg"
    # and one with photo_path="site-note.jpg" (legacy free text).
    # Act: GET /api/v1/incidents/{incident_id} exactly as the neighbouring tests do.
    items = response.json()["confirmed_reports"]["items"]
    by_photo = {item["photo_available"]: item for item in items}
    assert by_photo[True]["photo_url"] == (
        "/api/v1/photos/30000000-0000-0000-0000-000000000001"
    )
    legacy = next(item for item in items if item["photo_url"] is None)
    assert legacy["photo_available"] is True or legacy["photo_available"] is False
```

Adjust the arrange section to this file's actual fixture helpers when writing it; both complaints have non-null `photo_path`, so assert precisely: the uploads-path complaint has the URL, the legacy one has `photo_url is None` while `photo_available is True`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run --offline python -m pytest tests/contract/test_incident_read_api.py -q`
Expected: the new test FAILS with a KeyError on `photo_url`.

- [ ] **Step 3: Add the field and projection**

In `src/civicpulse/api/dto/incidents.py`:

```python
class ComplaintSummaryResponse(ApiModel):
    complaint_id: UUID
    text: str
    category: Category
    latitude: float
    longitude: float
    reported_at: datetime
    photo_available: bool
    photo_url: str | None
```

In `src/civicpulse/api/routes/incidents.py`, add the import `from civicpulse.photos import photo_url_for` and extend the `ComplaintSummaryResponse(...)` construction inside `get_incident`:

```python
photo_available=complaint.photo_path is not None,
photo_url=photo_url_for(complaint.photo_path),
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --offline python -m pytest tests/contract/test_incident_read_api.py -q` → green.
Run: `uv run --offline python -m pytest -q --deselect tests/contract/test_openapi_freeze.py` → green.
Run: `uv run --offline pyright src scripts` → 0 errors.

- [ ] **Step 5: Commit**

```powershell
git add src/civicpulse/api tests/contract/test_incident_read_api.py
git commit -m "feat(photos): incident detail evidence rows carry photo_url"
```

---

### Task 6: Runtime composition, health, and reset purge

**Files:**
- Modify: `src/civicpulse/runtime.py`
- Modify: `src/civicpulse/service.py`
- Test: extend `tests/integration/test_repository_photos.py` (service-level purge test)

**Interfaces:**
- Consumes: everything above
- Produces: `RuntimeSettings.uploads_path: Path = Path("data/uploads")` with env override `CIVICPULSE_UPLOADS_PATH`; `build_runtime` constructs `PhotoStore(resolved.uploads_path)`, passes `photo_healthcheck=photo_store.health_check` and `photo_store=photo_store` to `CivicPulseService`, and `photo_store=photo_store` to `create_app`; `CivicPulseService.__init__` gains keyword `photo_store: PhotoStore | None = None`; `reset_seed` purges photo rows and files after a successful seed import.

- [ ] **Step 1: Write the failing test (append to `tests/integration/test_repository_photos.py`)**

A focused test on the purge contract without composing the full runtime:

```python
def test_reset_purges_photo_rows_and_files(tmp_path: Path) -> None:
    from civicpulse.photos import PhotoStore

    repository = make_repository(tmp_path)
    store = PhotoStore(tmp_path / "uploads")
    stored = store.save(b"\xff\xd8\xff\xe0" + b"\x00" * 32)
    repository.add_photo(stored, created_at=NOW)

    # Mirrors the reset_seed purge sequence.
    assert repository.purge_photos() == 1
    assert store.purge() == 1
    assert repository.get_photo(stored.photo_id) is None
```

Additionally add a unit test asserting the service wiring in `tests/unit/test_photo_store.py`:

```python
def test_service_reset_purges_photos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from civicpulse.service import CivicPulseService

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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --offline python -m pytest tests/unit/test_photo_store.py tests/integration/test_repository_photos.py -q`
Expected: the service test FAILS (`photo_store` attribute and purge behavior missing).

- [ ] **Step 3: Update `src/civicpulse/service.py`**

Add the import `from civicpulse.photos import PhotoStore` (grouped with the other civicpulse imports). Extend the constructor keyword arguments:

```python
photo_store: PhotoStore | None = None,
```

and in the body, next to `self.photo_healthcheck = photo_healthcheck`:

```python
self.photo_store = photo_store
```

Replace `reset_seed`:

```python
def reset_seed(self, path: str | Path) -> SeedResult:
    result = self._import_seed(path)
    self.repository.purge_photos()
    if self.photo_store is not None:
        self.photo_store.purge()
    return result
```

- [ ] **Step 4: Update `src/civicpulse/runtime.py`**

Add `from civicpulse.photos import PhotoStore` to the imports. Add to `RuntimeSettings`:

```python
uploads_path: Path = Path("data/uploads")
```

and inside `from_environment`, add to the constructor call:

```python
uploads_path=Path(source.get("CIVICPULSE_UPLOADS_PATH", "data/uploads")),
```

In `build_runtime`, after `repository.initialize()`:

```python
photo_store = PhotoStore(resolved.uploads_path)
```

then extend the `CivicPulseService(...)` construction with:

```python
photo_healthcheck=photo_store.health_check,
photo_store=photo_store,
```

and the `create_app(...)` call with:

```python
photo_store=photo_store,
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run --offline python -m pytest tests/unit/test_photo_store.py tests/integration/test_repository_photos.py -q` → green.
Run: `uv run --offline python -m pytest -q --deselect tests/contract/test_openapi_freeze.py` → green. Watch the reset-related suites (`test_dashboard_reset.py`) in particular; the fake services there do not define `photo_store`, which is fine because the route calls `service.reset_seed` on the fake itself.
Run: `uv run --offline pyright src scripts` → 0 errors.
Health behavior note: with the store wired, `GET /api/v1/health/ready` now reports the photo provider as available (the existing `photo_healthcheck` hook), instead of "not configured".

- [ ] **Step 6: Commit**

```powershell
git add src/civicpulse/runtime.py src/civicpulse/service.py tests
git commit -m "feat(photos): compose photo store into runtime, health, and reset purge"
```

---

### Task 7: OpenAPI snapshot update and version bump

**Files:**
- Modify: `src/civicpulse/api/app.py` (version)
- Regenerate: `tests/contracts/openapi-v1.json`

**Interfaces:**
- Consumes: all backend changes (Tasks 3 to 6)
- Produces: a reviewed contract snapshot containing `photosUpload`, `photosGet`, `ComplaintCreateRequest.photo_id`, and `ComplaintSummaryResponse.photo_url`, with API version `1.1.0`.

- [ ] **Step 1: Bump the version**

In `src/civicpulse/api/app.py`, change `version: str = "1.0.0"` to `version: str = "1.1.0"`.

- [ ] **Step 2: Regenerate the snapshot explicitly**

Run: `uv run --offline python -m scripts.update_openapi_snapshot`
Expected: prints the snapshot path. Inspect the diff of `tests/contracts/openapi-v1.json` and confirm it contains ONLY: the two `/api/v1/photos` operations, `photo_id` on `ComplaintCreateRequest`, `photo_url` on `ComplaintSummaryResponse`, the new `PhotoUploadResponse` schema, and the version bump. Any other drift means an accidental contract change; stop and fix before committing.

- [ ] **Step 3: Full backend verification**

Run and record actual output:

```powershell
uv run --offline python -m pytest -q
uv run --offline pyright src scripts
uv run --offline ruff check src/civicpulse_dashboard
git diff --check
```

Expected: full suite green including `test_openapi_freeze.py`; 0 pyright errors; ruff clean.

- [ ] **Step 4: Commit**

```powershell
git add src/civicpulse/api/app.py tests/contracts/openapi-v1.json
git commit -m "feat(api): publish v1.1.0 contract with photo storage endpoints"
```

---

### Task 8: Frontend photo upload port, adapter, and application service

**Files:**
- Regenerate: `frontend/src/features/incidents/adapters/http/generated/openapi.d.ts`
- Create: `frontend/src/features/submissions/application/photo-upload-port.ts`
- Create: `frontend/src/features/submissions/application/upload-photo.ts`
- Create: `frontend/src/features/submissions/adapters/http/photo-http-adapter.ts`
- Test: `frontend/src/features/submissions/adapters/http/photo-http-adapter.spec.ts`

All frontend commands run inside `frontend/` with pnpm.

**Interfaces:**
- Consumes: the regenerated OpenAPI types; `fetch` injection pattern from `complaint-http-adapter.ts`
- Produces:

```ts
type PhotoUploadError =
  | { kind: "network" } | { kind: "aborted" }
  | { kind: "unsupported"; status: number }
  | { kind: "too_large"; status: number }
  | { kind: "service"; status: number }
  | { kind: "contract" }
type PhotoUploadResult =
  | { ok: true; photoId: string }
  | { ok: false; error: PhotoUploadError }
interface PhotoUploadPort { upload(file: File, signal: AbortSignal): Promise<PhotoUploadResult> }
class UploadPhoto { execute(file: File, signal: AbortSignal): Promise<PhotoUploadResult> }
class PhotoHttpAdapter implements PhotoUploadPort
```

- [ ] **Step 1: Regenerate the API types**

Run: `pnpm run api:generate`
Expected: `generated/openapi.d.ts` gains the photos paths and `PhotoUploadResponse`. `pnpm run api:check` passes.

- [ ] **Step 2: Write the failing adapter spec `photo-http-adapter.spec.ts`**

```ts
import { describe, expect, it, vi } from "vitest"

import { PhotoHttpAdapter } from "./photo-http-adapter"

const PHOTO_ID = "30000000-0000-0000-0000-000000000001"

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function jpegFile(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], "evidence.jpg", {
    type: "image/jpeg",
  })
}

describe("PhotoHttpAdapter", () => {
  it("posts multipart form data and returns the photo id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ photo_id: PHOTO_ID, media_type: "image/jpeg", byte_size: 4 }, 201),
    )
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result).toEqual({ ok: true, photoId: PHOTO_ID })
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/v1/photos")
    expect(init.method).toBe("POST")
    expect(init.body).toBeInstanceOf(FormData)
    const sent = (init.body as FormData).get("file")
    expect(sent).toBeInstanceOf(File)
  })

  it.each([
    [415, "unsupported"],
    [413, "too_large"],
    [500, "service"],
  ])("maps HTTP %d to the %s error kind", async (status, kind) => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ error: { code: "x", message: "x", details: {}, request_id: "r" } }, status),
    )
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error.kind).toBe(kind)
  })

  it("maps thrown fetch failures to network errors", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"))
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result).toEqual({ ok: false, error: { kind: "network" } })
  })

  it("rejects malformed success payloads as contract errors", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ photo_id: "not-a-uuid" }, 201))
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result).toEqual({ ok: false, error: { kind: "contract" } })
  })
})
```

- [ ] **Step 3: Run to verify failure**

Run: `pnpm vitest run src/features/submissions/adapters/http/photo-http-adapter.spec.ts`
Expected: FAIL, module not found.

- [ ] **Step 4: Write `application/photo-upload-port.ts`**

```ts
export type PhotoUploadError =
  | { readonly kind: "network" }
  | { readonly kind: "aborted" }
  | { readonly kind: "unsupported"; readonly status: number }
  | { readonly kind: "too_large"; readonly status: number }
  | { readonly kind: "service"; readonly status: number }
  | { readonly kind: "contract" }

export type PhotoUploadResult =
  | { readonly ok: true; readonly photoId: string }
  | { readonly ok: false; readonly error: PhotoUploadError }

export interface PhotoUploadPort {
  upload(file: File, signal: AbortSignal): Promise<PhotoUploadResult>
}
```

- [ ] **Step 5: Write `application/upload-photo.ts`**

```ts
import type { PhotoUploadPort, PhotoUploadResult } from "./photo-upload-port"

export class UploadPhoto {
  constructor(private readonly port: PhotoUploadPort) {}

  execute(file: File, signal: AbortSignal): Promise<PhotoUploadResult> {
    return this.port.upload(file, signal)
  }
}
```

- [ ] **Step 6: Write `adapters/http/photo-http-adapter.ts`**

```ts
import type {
  PhotoUploadPort,
  PhotoUploadResult,
} from "../../application/photo-upload-port"

interface PhotoHttpAdapterDependencies {
  readonly baseUrl: string
  readonly fetch: typeof globalThis.fetch
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function isAbortError(error: unknown): boolean {
  return typeof error === "object" && error !== null && "name" in error && error.name === "AbortError"
}

function decodePhotoId(value: unknown): string {
  if (typeof value !== "object" || value === null || !("photo_id" in value)) {
    throw new TypeError("Invalid photo-upload response")
  }
  const photoId = (value as { photo_id: unknown }).photo_id
  if (typeof photoId !== "string" || !UUID_PATTERN.test(photoId)) {
    throw new TypeError("Invalid photo-upload response")
  }
  return photoId
}

export class PhotoHttpAdapter implements PhotoUploadPort {
  constructor(private readonly dependencies: PhotoHttpAdapterDependencies) {}

  async upload(file: File, signal: AbortSignal): Promise<PhotoUploadResult> {
    const body = new FormData()
    body.append("file", file, file.name)
    let response: Response
    try {
      response = await this.dependencies.fetch(`${this.dependencies.baseUrl}/photos`, {
        method: "POST",
        body,
        signal,
      })
    } catch (error: unknown) {
      return { ok: false, error: { kind: isAbortError(error) ? "aborted" : "network" } }
    }
    if (response.status === 415) return { ok: false, error: { kind: "unsupported", status: 415 } }
    if (response.status === 413) return { ok: false, error: { kind: "too_large", status: 413 } }
    if (!response.ok) return { ok: false, error: { kind: "service", status: response.status } }
    try {
      return { ok: true, photoId: decodePhotoId(await response.json()) }
    } catch (error: unknown) {
      return { ok: false, error: { kind: isAbortError(error) ? "aborted" : "contract" } }
    }
  }
}
```

- [ ] **Step 7: Run to verify pass**

Run: `pnpm vitest run src/features/submissions/adapters/http/photo-http-adapter.spec.ts`
Expected: 6 passed.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/features/submissions frontend/src/features/incidents/adapters/http/generated
git commit -m "feat(frontend): photo upload port, adapter, and application service"
```

---

### Task 9: Submission flow uploads on selection and sends `photo_id`

**Files:**
- Modify: `frontend/src/features/submissions/domain/complaint.ts`
- Modify: `frontend/src/features/submissions/adapters/http/complaint-http-adapter.ts`
- Modify: `frontend/src/features/submissions/ui/SubmitPage.vue`
- Modify: `frontend/src/composition/create-app-services.ts`
- Modify: `frontend/src/App.vue` (pass the new prop where `SubmitPage` is rendered)
- Test: extend `frontend/src/features/submissions/ui/SubmitPage.spec.ts` and `complaint-http-adapter.spec.ts`

**Interfaces:**
- Consumes: `UploadPhoto` (Task 8), existing `useComplaintSubmission` (unchanged)
- Produces: `ComplaintSubmissionRequest.photoPath` replaced by `photoId: string | null`; `SubmittedComplaint` becomes a standalone interface that keeps `photoPath: string | null` (it mirrors the response, which still returns the server-owned `photo_path`); the complaint adapter sends `photo_id`; `SubmitPage` uploads the photo immediately after validation/preview/GPS, blocks submission while uploading, surfaces upload errors with retry, and passes the uploaded `photoId` on submit; `createAppServices` exposes `uploadPhoto: UploadPhoto`.

- [ ] **Step 1: Update the domain types in `domain/complaint.ts`**

Replace `ComplaintSubmissionRequest` and `SubmittedComplaint`:

```ts
export interface ComplaintSubmissionRequest {
  readonly text: string
  readonly latitude: number
  readonly longitude: number
  readonly reportedAt: string
  readonly category: IncidentCategory | null
  readonly photoId: string | null
}

export interface SubmittedComplaint {
  readonly complaintId: string
  readonly text: string
  readonly latitude: number
  readonly longitude: number
  readonly reportedAt: string
  readonly category: IncidentCategory | null
  readonly photoPath: string | null
}
```

- [ ] **Step 2: Update `complaint-http-adapter.ts`**

In the JSON body, replace `photo_path: request.photoPath,` with `photo_id: request.photoId,`. Update the neighbouring `complaint-http-adapter.spec.ts` expectations accordingly (the recorded body now carries `photo_id`).

- [ ] **Step 3: Write the failing SubmitPage specs (extend `SubmitPage.spec.ts`)**

Follow the file's existing mounting pattern (it stubs `submitComplaint` with a `Pick<SubmitComplaint, "execute">`). Add a stub `uploadPhoto` prop and these cases:

```ts
it("uploads the photo on selection and passes its id on submit", async () => {
  const uploadPhoto = { execute: vi.fn().mockResolvedValue({ ok: true, photoId: PHOTO_ID }) }
  const submitComplaint = { execute: vi.fn().mockResolvedValue(SUCCESS_RESULT) }
  // mount with both props, set a JPEG file on the file input, flush promises,
  // fill text/latitude/longitude, submit the form
  expect(uploadPhoto.execute).toHaveBeenCalledTimes(1)
  const [request] = submitComplaint.execute.mock.calls[0]
  expect(request.photoId).toBe(PHOTO_ID)
})

it("blocks submission while the photo upload is in flight", async () => {
  // uploadPhoto.execute returns a pending promise; after selecting the file,
  // the submit button is disabled and shows the uploading label
})

it("shows the upload error and submits without a photo after removal", async () => {
  // uploadPhoto.execute resolves { ok: false, error: { kind: "service", status: 500 } };
  // the error text renders; clicking "Remove photo" clears it;
  // submitting then passes photoId: null
})
```

Write these as complete tests against the real component using the file's established helpers (file inputs are set via `Object.defineProperty(input.element, "files", ...)` plus a change event, as the existing photo tests in this spec already do).

- [ ] **Step 4: Run to verify failure**

Run: `pnpm vitest run src/features/submissions/ui/SubmitPage.spec.ts`
Expected: new tests FAIL (`uploadPhoto` prop unknown, `photoId` not sent).

- [ ] **Step 5: Update `SubmitPage.vue`**

Script changes (complete replacement of the affected parts):

```ts
import type { UploadPhoto } from "../application/upload-photo"

const props = defineProps<{
  readonly submitComplaint: Pick<SubmitComplaint, "execute">
  readonly uploadPhoto: Pick<UploadPhoto, "execute">
}>()

type PhotoUploadState =
  | { readonly kind: "none" }
  | { readonly kind: "uploading" }
  | { readonly kind: "uploaded"; readonly photoId: string }
  | { readonly kind: "failed"; readonly message: string }

const photoUpload = ref<PhotoUploadState>({ kind: "none" })
let uploadController: AbortController | null = null

function uploadErrorMessage(kind: string): string {
  switch (kind) {
    case "network": return "The photo could not be uploaded because the API is unreachable. Remove it or try again."
    case "unsupported": return "The API rejected this file; use a JPEG or PNG photo."
    case "too_large": return "The API rejected this photo; keep it under 8 MB."
    default: return "The photo could not be uploaded. Remove it or try again."
  }
}

async function startUpload(file: File): Promise<void> {
  uploadController?.abort()
  const controller = new AbortController()
  uploadController = controller
  photoUpload.value = { kind: "uploading" }
  const result = await props.uploadPhoto.execute(file, controller.signal)
  if (controller.signal.aborted || selectedFile.value !== file) return
  uploadController = null
  photoUpload.value = result.ok
    ? { kind: "uploaded", photoId: result.photoId }
    : result.error.kind === "aborted"
      ? { kind: "none" }
      : { kind: "failed", message: uploadErrorMessage(result.error.kind) }
}

function retryUpload(): void {
  if (selectedFile.value !== null) void startUpload(selectedFile.value)
}
```

Extend `clearPhoto()` with (at the top of the function):

```ts
uploadController?.abort()
uploadController = null
photoUpload.value = { kind: "none" }
```

In `onPhotoChange`, after `photoPreviewUrl.value = URL.createObjectURL(file)`, add:

```ts
void startUpload(file)
```

Replace the `photoPath` line in `submit()` and gate on the upload state:

```ts
function submit(): void {
  if (!validateForm()) return
  if (photoUpload.value.kind === "uploading") {
    formError.value = "Wait for the photo upload to finish, or remove the photo."
    return
  }
  if (photoUpload.value.kind === "failed") {
    formError.value = "Retry or remove the failed photo upload before submitting."
    return
  }
  void submission.submit({
    text: text.value.trim(),
    latitude: Number(latitude.value),
    longitude: Number(longitude.value),
    reportedAt: new Date().toISOString(),
    category: category.value === "" ? null : category.value,
    photoId: photoUpload.value.kind === "uploaded" ? photoUpload.value.photoId : null,
  })
}
```

The `safeFileName` helper is no longer used; delete it. Template changes inside the preview block: replace the static filename/GPS paragraph area with upload status, and update the two copy strings that claimed the photo is not uploaded:

- Help text under the file input becomes: `JPEG or PNG, up to 8 MB. The photo is stored with the report and appears in the incident detail.`
- Header description becomes: `Add a text report, location, and optional photo evidence. Photos upload to the local CivicPulse server.`

Inside `.submit-page__preview` details `<div>`:

```vue
<p>{{ selectedFile?.name }}</p>
<p v-if="photoUpload.kind === 'uploading'" class="submit-page__help" role="status">
  Uploading photo…
</p>
<p v-else-if="photoUpload.kind === 'uploaded'" class="submit-page__help">
  Photo uploaded and ready to attach.
</p>
<p v-else-if="photoUpload.kind === 'failed'" class="submit-page__error" role="alert">
  {{ photoUpload.message }}
</p>
<button
  v-if="photoUpload.kind === 'failed'"
  type="button"
  @click="retryUpload"
>
  Retry upload
</button>
<p v-if="gpsFromPhoto" class="submit-page__help">
  Coordinates filled from photo GPS metadata.
</p>
<button type="button" @click="clearPhoto">Remove photo</button>
```

Submit button label/disabled state:

```vue
<button
  type="submit"
  :disabled="state.kind === 'submitting' || photoUpload.kind === 'uploading'"
>
  {{ state.kind === "submitting" ? "Submitting…" : photoUpload.kind === "uploading" ? "Waiting for photo upload…" : "Submit report" }}
</button>
```

Success panel: the `photoPath` note still works (response carries the server path); update its copy to: `Photo stored as {{ state.submission.complaint.photoPath }}. It will appear in the incident detail.`

- [ ] **Step 6: Wire composition**

In `create-app-services.ts`, add imports for `PhotoHttpAdapter` and `UploadPhoto`, add `readonly uploadPhoto: UploadPhoto` to `AppServices`, construct `const photos = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: window.fetch.bind(window) })`, and return `uploadPhoto: new UploadPhoto(photos)`. In `App.vue`, add `:upload-photo="services.uploadPhoto"` (matching the existing prop-binding style) where `<SubmitPage ... :submit-complaint="..." />` is rendered.

- [ ] **Step 7: Run to verify pass**

Run: `pnpm vitest run src/features/submissions` → green.
Run: `pnpm run check` → api:check, lint, all tests, and build pass.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src
git commit -m "feat(frontend): upload photo evidence on selection and submit photo_id"
```

---

### Task 10: Incident detail renders photo evidence

**Files:**
- Modify: `frontend/src/features/incidents/domain/incident.ts`
- Modify: `frontend/src/features/incidents/adapters/http/decode-incident-detail.ts`
- Modify: `frontend/src/features/incidents/testing/incident-fixtures.ts`
- Modify: `frontend/src/features/incidents/ui/IncidentDetailPage.vue`
- Test: extend `decode-incident-detail.spec.ts` and `IncidentDetailPage.spec.ts`

**Interfaces:**
- Consumes: `photo_url` from the v1.1.0 contract (Task 5)
- Produces: `IncidentComplaintSummary.photoUrl: string | null`; the strict decoder accepts exactly the new key set (`photo_url` added to `COMPLAINT_KEYS`) and validates the URL shape; `IncidentDetailPage.vue` renders a lazy-loaded thumbnail linking to the full image, with an explicit line for legacy photo references.

- [ ] **Step 1: Write the failing decoder specs (extend `decode-incident-detail.spec.ts`)**

Using the file's existing valid-payload builder, add:

```ts
it("decodes photo_url into photoUrl", () => {
  const payload = buildValidDetailPayload()
  payload.confirmed_reports.items[0].photo_url =
    "/api/v1/photos/30000000-0000-0000-0000-000000000001"
  const detail = decodeIncidentDetail(payload)
  expect(detail.confirmedReports.items[0].photoUrl).toBe(
    "/api/v1/photos/30000000-0000-0000-0000-000000000001",
  )
})

it("accepts a null photo_url", () => {
  const payload = buildValidDetailPayload()
  payload.confirmed_reports.items[0].photo_url = null
  expect(decodeIncidentDetail(payload).confirmedReports.items[0].photoUrl).toBeNull()
})

it("rejects complaint rows without photo_url", () => {
  const payload = buildValidDetailPayload()
  delete payload.confirmed_reports.items[0].photo_url
  expect(() => decodeIncidentDetail(payload)).toThrowError(TypeError)
})

it("rejects photo_url values outside the photos endpoint", () => {
  const payload = buildValidDetailPayload()
  payload.confirmed_reports.items[0].photo_url = "https://evil.example/x.jpg"
  expect(() => decodeIncidentDetail(payload)).toThrowError(TypeError)
})
```

Adapt `buildValidDetailPayload` to whatever helper the spec actually uses; fixtures must first gain `photo_url` (next step) or these tests cannot compile.

- [ ] **Step 2: Update fixtures, domain, and decoder**

`incident-fixtures.ts`: every complaint-summary transport object gains `photo_url: null` (or a valid `/api/v1/photos/{uuid}` where a fixture already sets `photo_available: true`), and every domain-side complaint summary gains the matching `photoUrl`.

`domain/incident.ts`:

```ts
export interface IncidentComplaintSummary {
  readonly complaintId: string
  readonly text: string
  readonly category: IncidentCategory
  readonly latitude: number
  readonly longitude: number
  readonly reportedAt: string
  readonly photoAvailable: boolean
  readonly photoUrl: string | null
}
```

`decode-incident-detail.ts`: add `"photo_url"` to `COMPLAINT_KEYS`, add the validator and use it:

```ts
const PHOTO_URL_PATTERN =
  /^\/api\/v1\/photos\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function decodePhotoUrl(value: unknown): string | null {
  if (value === null) return null
  const url = requireString(value)
  if (!PHOTO_URL_PATTERN.test(url)) return invalidResponse()
  return url
}
```

and in `decodeComplaintSummary`, add `photoUrl: decodePhotoUrl(value.photo_url),`.

- [ ] **Step 3: Run decoder specs to verify pass**

Run: `pnpm vitest run src/features/incidents/adapters/http/decode-incident-detail.spec.ts`
Expected: green, including the four new cases.

- [ ] **Step 4: Write the failing page specs (extend `IncidentDetailPage.spec.ts`)**

```ts
it("renders a photo thumbnail linking to the stored image", async () => {
  // fixture detail whose first confirmed report has
  // photoUrl "/api/v1/photos/30000000-0000-0000-0000-000000000001"
  const image = wrapper.get("[data-report-photo]")
  expect(image.attributes("src")).toBe("/api/v1/photos/30000000-0000-0000-0000-000000000001")
  expect(image.attributes("loading")).toBe("lazy")
  const link = wrapper.get("[data-report-photo-link]")
  expect(link.attributes("href")).toBe("/api/v1/photos/30000000-0000-0000-0000-000000000001")
})

it("explains legacy photo references without an image", async () => {
  // fixture report with photoAvailable: true and photoUrl: null
  expect(wrapper.text()).toContain("Photo reference recorded before server storage")
  expect(wrapper.find("[data-report-photo]").exists()).toBe(false)
})
```

- [ ] **Step 5: Update `IncidentDetailPage.vue`**

Replace the report `<li>` body (currently text plus the `Photo available` line) with:

```vue
<li
  v-for="report in readyDetail.confirmedReports.items"
  :key="report.complaintId"
>
  <p>{{ report.text }}</p>
  <small>
    {{ report.category }} · {{ report.latitude.toFixed(4) }}, {{ report.longitude.toFixed(4) }}
  </small>
  <a
    v-if="report.photoUrl !== null"
    class="incident-detail__photo-link"
    :href="report.photoUrl"
    target="_blank"
    rel="noopener"
    data-report-photo-link
  >
    <img
      class="incident-detail__photo"
      :src="report.photoUrl"
      loading="lazy"
      :alt="`Photo evidence for report ${report.complaintId.slice(0, 8)}`"
      data-report-photo
    >
  </a>
  <small v-else-if="report.photoAvailable">
    Photo reference recorded before server storage; image unavailable.
  </small>
  <small v-else>No photo evidence.</small>
</li>
```

Add to the component's scoped styles (matching the page's existing token usage):

```css
.incident-detail__photo-link {
  display: inline-block;
  margin-top: 0.5rem;
}

.incident-detail__photo {
  display: block;
  max-width: 14rem;
  max-height: 10rem;
  object-fit: cover;
  border: 1px solid var(--divider);
}
```

- [ ] **Step 6: Run to verify pass**

Run: `pnpm vitest run src/features/incidents` → green.
Run: `pnpm run check` → all gates pass.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src
git commit -m "feat(frontend): render stored photo evidence in incident detail"
```

---

### Task 11: End-to-end verification and documentation

**Files:**
- Modify: `README.md` (API surface table + photo feature note)
- Modify: any file failing verification

**Interfaces:**
- Consumes: everything above
- Produces: a demo-verified, documented feature.

- [ ] **Step 1: Full automated verification**

Backend (repo root):

```powershell
uv run --offline python -m pytest -q
uv run --offline pyright src scripts
uv run --offline ruff check src/civicpulse_dashboard
git diff --check
```

Frontend (`frontend/`): `pnpm run check`
Expected: everything green.

- [ ] **Step 2: Live end-to-end walk**

Start the API (`uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000`) and the frontend (`pnpm dev`), then:

1. Submit a report with a real JPEG attached. The preview shows "Uploading photo…" then "Photo uploaded and ready to attach"; the success panel shows the stored `uploads/{uuid}.jpg` path.
2. Confirm `data/uploads/` contains one `{uuid}.jpg` file and the `photos` table one row (`uv run --offline python -c "import sqlite3; print(sqlite3.connect('data/civicpulse.db').execute('select photo_id, media_type, byte_size from photos').fetchall())"`).
3. Open the incident queue, open the detail of the incident containing the new report. The photo thumbnail renders; clicking it opens the full image served with `Content-Type: image/jpeg`.
4. Seeded complaints and pre-feature submissions show either "No photo evidence." or the legacy-reference line, never a broken image.
5. Try uploading a renamed `.jpg` that is actually a text file → inline error "The API rejected this file; use a JPEG or PNG photo."
6. With `CIVICPULSE_ADMIN_RESET_ENABLED=true`, trigger the demo reset and confirm `data/uploads/` is empty and the `photos` table has zero rows afterwards.
7. Health check: `GET /api/v1/health/ready` reports the photo provider as available.

- [ ] **Step 3: Update `README.md`**

In the API surface table, add:

```markdown
| Photos | `POST /api/v1/photos` (multipart upload), `GET /api/v1/photos/{photo_id}` |
```

Below the table, add one paragraph: photo evidence is stored as files under `data/uploads/` (configurable via `CIVICPULSE_UPLOADS_PATH`) with metadata in SQLite; media types come from content sniffing; the demo reset purges stored photos; the API version is 1.1.0.

Also update the "Current boundaries and limitations" bullet about photo analysis: storage and rendering now exist; automated photo analysis remains out of scope.

- [ ] **Step 4: Commit**

```powershell
git add README.md
git commit -m "docs: document photo evidence storage endpoints and reset behavior"
```

---

## Self-Review

- **Spec coverage:** store images server-side and render them in incident detail (Tasks 1 to 5, 10), local disk + SQLite metadata rather than BLOBs (Tasks 1 and 2, rationale section), `GET /api/v1/photos/{photo_id}` serving with correct media type (Task 3), explicit OpenAPI snapshot update as its own reviewed step (Task 7, Global Constraints), client never supplies storage paths (`photo_id` flow in Task 4 with the reserved-prefix guard), magic-byte sniffing + `nosniff` + UUID filenames (Tasks 1 and 3), reset purges uploads (Task 6), photo provider health check wired (Task 6), Streamlit compatibility preserved (Task 4 keeps `photo_path`, dashboard gateway tests re-run), frontend upload + rendering (Tasks 8 to 10), end-to-end verification (Task 11).
- **Placeholder scan:** Task 5 Step 1 and Task 9 Step 3 intentionally defer to the target spec files' existing fixture helpers (which the implementer sees in full when editing those files) while stating the exact assertions and data; all other steps carry complete code.
- **Type consistency:** `StoredPhoto` fields (`photo_id`, `media_type`, `byte_size`, `stored_name`) match across `photos.py`, repository methods, and route usage; `photo_path_for`/`photo_url_for` produce and parse the same `uploads/{uuid}.{ext}` format; `PhotoUploadResult`/`PhotoUploadError` shapes match between port, adapter, adapter spec, and SubmitPage state handling; `photoUrl` naming matches domain, decoder, fixtures, and template; `create_app(photo_store=...)` parameter name matches tests and runtime wiring.
- **Ordering hazard acknowledged:** `test_openapi_freeze.py` is red from Task 3 until Task 7 regenerates the snapshot; interim steps deselect it explicitly, and Task 7 restores a fully green suite before any frontend work starts.
