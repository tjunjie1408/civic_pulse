# Task 7.5 OpenAPI Contract Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Freeze the `/api/v1` HTTP contract as a canonical, reviewable OpenAPI snapshot with explicit update tooling and semantic regression tests.

**Architecture:** Generate the document only from `create_app().openapi()`. Canonicalization sorts JSON object keys and the specified unordered arrays without deleting or rewriting contract fields. Tests compare generated canonical JSON to the committed snapshot and separately assert high-value semantics; the update command is never called by tests.

**Tech Stack:** Python 3.12, FastAPI 0.139.0, Pydantic 2.13.4, JSON, pytest.

## Global Constraints

- Canonicalization may reorder only semantically unordered structures and must preserve required, nullable/`anyOf` null, headers, enums, descriptions, status codes, references, and security/default behavior.
- Snapshot generation must use `create_app()` and must not initialize services, databases, models, or seeds.
- Snapshot comparison must fail when generated output differs; tests must never update the committed file.
- Runtime UTC serialization is tested separately from OpenAPI `format: date-time`.
- No client generation or UI changes are part of this task.

---

### Task 1: Write failing snapshot and semantic contract tests

**Files:**
- Create: `tests/contract/test_openapi_freeze.py`
- Create: `tests/contracts/README.md`

- [ ] Test full canonical snapshot equality against `tests/contracts/openapi-v1.json`.
- [ ] Test repeated `create_app().openapi()` canonicalization is byte-identical, operation IDs are unique, all public paths use `/api/v1`, and the route set is explicit.
- [ ] Test complaint idempotency header/409 schema, review approve/reject request and error schemas, nullable conflict priority, reset-disabled/no-body behavior, strict request schemas, stable error envelope references, and runtime UTC `Z` serialization.
- [ ] Run `uv run --offline python -m pytest tests/contract/test_openapi_freeze.py -q` and confirm the new tests fail because the snapshot/tooling does not yet exist.

### Task 2: Implement canonical generation and explicit update tooling

**Files:**
- Create: `scripts/openapi_snapshot.py`
- Create: `scripts/generate_openapi_snapshot.py`
- Create: `scripts/update_openapi_snapshot.py`

- [ ] Implement `canonicalize_openapi(document)` preserving all fields while sorting object keys, paths, schemas, response codes, parameters, and tags deterministically.
- [ ] Implement a generator requiring an explicit `--output` path and writing canonical JSON only; it must not know or overwrite the committed snapshot by default.
- [ ] Implement a separate explicit updater targeting `tests/contracts/openapi-v1.json`.
- [ ] Run focused tests and the generator to a workspace-local temporary output.

### Task 3: Create and validate the committed v1 snapshot

**Files:**
- Create: `tests/contracts/openapi-v1.json`

- [ ] Generate the snapshot explicitly with `uv run --offline python scripts/update_openapi_snapshot.py`.
- [ ] Run full snapshot and semantic tests; verify the committed snapshot contains the complete schemas, headers, response codes, descriptions, enums, nullable forms, and references.
- [ ] Confirm rerunning generation to a separate temporary path produces byte-identical JSON.

### Task 4: Run the full verification gate

**Files:**
- No additional files unless verification identifies a contract defect.

- [ ] Run all unit, integration, and contract tests in a workspace-local temporary directory.
- [ ] Run `uv run --offline pyright src scripts`, targeted Ruff for the API and new OpenAPI tooling/tests, and `git diff --check`; record unrelated legacy Ruff findings without expanding scope.
- [ ] Report the known FastAPI/httpx warning separately and stop at the review/commit gate.
