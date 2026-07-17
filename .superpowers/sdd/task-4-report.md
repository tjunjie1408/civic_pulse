# Task 4 Report: Complaint submission accepts `photo_id`

Date: 2026-07-17
Branch: `feat/photo-evidence-storage`
Worktree: `D:\self-learning\codex_hackathon\.worktrees\photo-evidence-storage`

## Scope completed

- Added failing contract coverage for complaint submission with uploaded photo references.
- Extended `ComplaintCreateRequest` with `photo_id` while keeping legacy `photo_path`.
- Rejected reserved `uploads/` `photo_path` values and conflicting `photo_id` + `photo_path`.
- Resolved `photo_id` to a server-owned `photo_path` in the complaint mutation route.
- Rejected unknown `photo_id` values with `unknown_photo` / 422.
- Preserved non-photo complaint submissions by letting the app reuse `service.repository` when no repository is injected separately.

## Files changed

- `src/civicpulse/api/app.py`
- `src/civicpulse/api/dto/complaints.py`
- `src/civicpulse/api/routes/mutations.py`
- `tests/contract/test_mutation_api.py`
- `tests/contract/test_photo_api.py`

## TDD evidence

1. Added four Task 4 contract tests in `tests/contract/test_photo_api.py`.
2. Ran:

   `uv run --offline python -m pytest tests/contract/test_photo_api.py -q`

3. Observed red state:
   - `photo_id` submission returned 422 instead of 201.
   - unknown `photo_id` returned `validation_error` instead of `unknown_photo`.
   - reserved `uploads/...` `photo_path` still returned 201.

## Verification

### Focused Task 4 checks

- `uv run --offline python -m pytest tests/contract/test_photo_api.py tests/contract/test_mutation_api.py tests/contract/test_dashboard_submission.py -q`
  - Result: `31 passed, 1 warning`

- `uv run --offline pyright src scripts`
  - Result: `0 errors, 0 warnings, 0 informations`

### Broader non-freeze pytest run

- `uv run --offline python -m pytest -q --deselect tests/contract/test_openapi_freeze.py`
  - Result: 1 unrelated pre-existing failure outside Task 4 scope:
    - `tests/contract/test_dashboard_review_reads.py::test_review_and_incident_models_match_frozen_read_contract`
    - failure reason: frozen read-contract schema still includes `confirmed_reports` while generated model fields do not.

## Notes / concerns

- I did not modify the OpenAPI freeze snapshot, per Task 7 ownership.
- The broader deselected pytest run is not fully green due the unrelated read-contract mismatch above.
- Dashboard submission behavior remains covered by the focused passing contract tests.
