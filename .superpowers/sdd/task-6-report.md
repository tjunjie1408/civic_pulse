# Task 6 Report — Runtime composition, health, and reset purge

Status: complete

## What changed

- Added the required failing-first coverage for Task 6:
  - `tests/unit/test_photo_store.py::test_service_reset_purges_photos`
  - `tests/integration/test_repository_photos.py::test_reset_purges_photo_rows_and_files`
- Extended `CivicPulseService` to accept an optional `photo_store` dependency and made `reset_seed()` purge persisted photo rows after a successful seed import, then purge on-disk uploads when a store is configured.
- Extended `RuntimeSettings` with `uploads_path` plus `CIVICPULSE_UPLOADS_PATH`.
- Updated `build_runtime()` to compose a `PhotoStore`, wire its health check into `CivicPulseService`, inject the store into the service, and pass the same store to `create_app()`.
- Tightened runtime composition coverage in `tests/integration/test_runtime_composition.py` so the composed runtime now proves:
  - the uploads path is sourced from runtime settings;
  - the composed app and service share the same `PhotoStore`;
  - `/api/v1/health/ready` reports the photo provider as healthy.

## Verification

- `uv run --offline python -m pytest tests/unit/test_photo_store.py tests/integration/test_repository_photos.py -q`
  - expected failing-first check reproduced before implementation: `test_service_reset_purges_photos`
- `uv run --offline python -m pytest tests/unit/test_photo_store.py tests/integration/test_repository_photos.py tests/integration/test_runtime_composition.py tests/contract/test_api_boundary.py tests/contract/test_mutation_api.py -q`
- `uv run --offline pyright src scripts`

All post-change verification passed.

## Concerns

- I did not update the OpenAPI snapshot, per the task boundary.
- I did not run the known slow full pytest invocation; the focused runtime/reset/health suite above passed and pyright was clean.
