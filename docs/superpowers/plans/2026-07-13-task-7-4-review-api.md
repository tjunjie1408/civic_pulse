# Task 7.4 Review API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose review reads and persistent approve/reject mutations without moving review or incident state transitions into the HTTP layer.

**Architecture:** Extend the existing review service boundary with read models that include the two complaints and persisted matcher evidence. Keep resolution orchestration in `CivicPulseService.resolve_review`; API routes only validate, map DTOs, and translate stable errors. Return incident snapshot transitions and affected incident priorities from the service result.

**Tech Stack:** Python 3.12, FastAPI, Pydantic strict DTOs, SQLite repository, pytest, Pyright, Ruff.

## Global Constraints

- Route handlers must not directly modify relationship, review, or incident persistence.
- Pending, approved, rejected, and conflict semantics must remain distinct.
- Incident IDs are membership-derived snapshot identifiers, not permanent case IDs.
- Original matcher evidence must be persisted and unchanged after resolution.
- Unknown and resolved review operations use stable API error codes.
- No authentication framework, background task, file upload, or generic admin surface.

---

### Task 1: Write failing review service and API contract tests

**Files:**
- Create: `tests/contract/test_review_api.py`
- Modify: `tests/integration/test_submission_service.py`

- [ ] Add tests for status filtering, deterministic pending/resolved ordering, pagination, detail evidence, 404, strict resolution payloads, approve/reject mutation results, resolved-review 409, conflict priority null, and restart persistence.
- [ ] Run `uv run --offline python -m pytest tests/contract/test_review_api.py tests/integration/test_submission_service.py -q` and confirm failures are caused by missing review API/service behavior.

### Task 2: Persist original matcher evidence and expose service review views

**Files:**
- Modify: `src/civicpulse/domain.py`
- Modify: `src/civicpulse/clustering.py`
- Modify: `src/civicpulse/repository.py`
- Modify: `src/civicpulse/service.py`

- [ ] Carry the original `MatchDecision` evidence through `RelationshipEdge` and review creation; add a nullable SQLite `matcher_evidence` column with migration support.
- [ ] Add `ReviewRead` and service methods for list/detail reads, keeping complaint lookup and review persistence inside the service boundary.
- [ ] Add typed `ReviewNotFound`, `ReviewAlreadyResolved`, and `ReviewStale` errors; preserve atomic repository resolution and return the resolved review, affected incidents, priorities, and snapshot IDs.
- [ ] Run the focused service tests and confirm they pass.

### Task 3: Implement strict review DTOs and routes

**Files:**
- Modify: `src/civicpulse/api/dto/reviews.py`
- Create: `src/civicpulse/api/routes/reviews.py`
- Modify: `src/civicpulse/api/app.py`

- [ ] Define strict list/detail/mutation response models with UTC datetimes, evidence fields, transition IDs, affected incidents, resulting priorities, and conflict status.
- [ ] Implement `GET /reviews`, `GET /reviews/{review_id}`, `POST /reviews/{review_id}/approve`, and `POST /reviews/{review_id}/reject` using the service methods and stable error mapping.
- [ ] Register the router without introducing import-time I/O or service construction.
- [ ] Run focused API tests and API Ruff/Pyright.

### Task 4: Full verification and review gate

**Files:**
- No additional files unless verification exposes a defect.

- [ ] Run the complete unit, integration, and contract suite in a workspace-local temporary directory.
- [ ] Run `uv run --offline pyright src scripts`, `uv run --offline ruff check src/civicpulse/api`, and `git diff --check`.
- [ ] Confirm the known FastAPI/httpx warning is unchanged and report the final evidence before commit.
