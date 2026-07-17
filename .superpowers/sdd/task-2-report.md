# Task 2 report: SQLite photo metadata

## Status

- Task status: Implemented
- Verification scope used: focused Task 2 integration test plus `pyright src scripts`
- Broad `pytest -q`: intentionally not awaited or used for completion because the repository baseline also times out and the user directed me to skip it

## Changed files

- `src/civicpulse/repository.py`
- `tests/integration/test_repository_photos.py`
- `.superpowers/sdd/task-2-report.md`

## Summary of changes

- Added `StoredPhoto` import to the repository module.
- Added additive `photos` table creation to `SQLiteRepository.initialize()` using `CREATE TABLE IF NOT EXISTS` and keeping schema version `1`.
- Added `SQLiteRepository.add_photo(photo: StoredPhoto, created_at: datetime) -> None`.
- Added `SQLiteRepository.get_photo(photo_id: UUID) -> StoredPhoto | None`.
- Added `SQLiteRepository.purge_photos() -> int`.
- Added integration coverage for add/get round-trip, missing-photo lookup, purge behavior, and initialize idempotency with persisted photo rows.

## Commit hash

- `b5f0b69`

## Test commands and output

### Red phase

Command:

```powershell
uv run --offline python -m pytest tests/integration/test_repository_photos.py -q
```

Observed result:

- Exit code: `1`
- `4 failed`
- Expected failure reason: `AttributeError: 'SQLiteRepository' object has no attribute 'add_photo'` / `get_photo`

### Green phase

Command:

```powershell
uv run --offline python -m pytest tests/integration/test_repository_photos.py -q
```

Observed result:

- Exit code: `0`
- Output: `4 passed in 0.73s`

### Type checking

Command:

```powershell
uv run --offline pyright src scripts
```

Observed result:

- Exit code: `0`
- Output: `0 errors, 0 warnings, 0 informations`

## Self-review

- Implemented the exact interface and SQL shape from the Task 2 brief.
- Kept the schema additive and idempotent by extending the existing `executescript` block with `CREATE TABLE IF NOT EXISTS photos (...)`.
- Matched the repository's existing transaction pattern using `BEGIN IMMEDIATE`, `commit()`, and `rollback()` on exceptions.
- Limited code changes to the repository file and the new Task 2 integration test; did not modify the OpenAPI snapshot or unrelated files.
- Verified the red/green cycle explicitly for the new integration test before completion.

## Concerns

- The broad `uv run --offline python -m pytest -q` check was not used for completion because the repository baseline also times out and the user explicitly instructed me to skip that broad run.
