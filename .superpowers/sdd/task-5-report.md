# Task 5 Report — Incident detail exposes `photo_url`

Status: complete

## What changed

- Added `photo_url: str | None` to `ComplaintSummaryResponse`.
- Projected `photo_url` in `GET /api/v1/incidents/{incident_id}` with `photo_url_for(complaint.photo_path)`.
- Kept `photo_available` semantics unchanged: any non-null `photo_path` still reports `photo_available=True`, including legacy free-text paths.
- Added a focused contract test covering:
  - a server-owned uploads path mapping to `/api/v1/photos/<uuid>`;
  - a legacy free-text `photo_path` mapping to `photo_url: null` while `photo_available` stays `true`.
- Updated the existing bounded-preview contract assertion to include the new nullable field.

## Verification

- `uv run --offline python -m pytest tests/contract/test_incident_read_api.py -q`
- `uv run --offline pyright src scripts`

Both passed.

## Concerns

- The task brief’s example server path used a non-v4 UUID-like string. The photo helper is intentionally strict and only derives URLs for server-owned v4 UUID filenames, so the new contract test uses a valid server-owned v4 path instead.
- OpenAPI freeze was intentionally not updated here, per the Task 7 boundary.
