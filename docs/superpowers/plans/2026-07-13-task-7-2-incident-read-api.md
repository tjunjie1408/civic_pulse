# Task 7.2 Incident Read API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose stable, read-only incident list and detail endpoints without reimplementing matching, clustering, or priority semantics in HTTP routes.

**Architecture:** Add a thin `IncidentQueryService` that reads persisted incidents and complaints, applies fixed deterministic filtering/paging, and computes the existing `PriorityAssessment` from the configured policy. Routes depend on that service and map internal read results to strict API DTOs; the existing Task 7.1 health routes and side-effect-free app factory remain unchanged.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLite repository, pytest, pyright, Ruff.

## Global Constraints

- Preserve the uncertainty boundary: confirmed membership and priority use confirmed evidence only; review candidates remain separate evidence.
- Conflict incidents expose `priority: null`; `review_required` is not an operational priority in the API.
- Incident IDs are membership-derived snapshot identifiers and may change when confirmed membership changes.
- `create_app()` must not initialize SQLite or load the embedding model.
- API DTOs use strict `extra="forbid"` models and routes do not expose domain models directly.
- Pagination uses `limit` in `1..100` and `offset >= 0`; ordering is priority descending, latest activity descending, then incident ID.

---

### Task 1: Define the query-service read boundary

**Files:**
- Create: `src/civicpulse/incident_query.py`
- Modify: `src/civicpulse/api/dependencies.py`
- Modify: `src/civicpulse/api/app.py`

**Interfaces:**
- Consumes: `SQLiteRepository.list_incidents()`, `SQLiteRepository.get_incident()`, `SQLiteRepository.list_complaints()`, `assess_priority()`, `PriorityPolicy`, and `SensitiveLocation`.
- Produces: `IncidentListQuery`, `IncidentRead`, `IncidentPage`, and `IncidentQueryService.list_incidents()` / `get_incident()` for API routes.

- [ ] Add immutable query/read models with explicit fields for incident snapshot, priority assessment, and evidence counts.
- [ ] Implement list filtering for status, priority, and category, fixed deterministic ordering, `limit`, `offset`, and total count.
- [ ] Implement detail lookup returning `None` for an unknown snapshot ID and preserving confirmed edges, review candidates, timestamps, centroid, radius, categories, and conflict reasons.
- [ ] Keep priority calculation in the query service using `assess_priority()` and return no priority for conflicts.
- [ ] Wire an injected query service through app state and dependency override support without constructing runtime services in `create_app()`.

### Task 2: Add strict incident response DTOs and routes

**Files:**
- Modify: `src/civicpulse/api/dto/incidents.py`
- Create: `src/civicpulse/api/dto/pagination.py`
- Create: `src/civicpulse/api/routes/incidents.py`
- Modify: `src/civicpulse/api/app.py`
- Modify: `src/civicpulse/api/errors.py`

**Interfaces:**
- Consumes: `IncidentPage`, `IncidentRead`, and the existing `ApiError` envelope.
- Produces: `GET /api/v1/incidents` and `GET /api/v1/incidents/{incident_id}` with stable operation IDs and OpenAPI schemas.

- [ ] Define strict list/detail DTOs for category summaries, priority, confirmed edges, review candidate summaries, radius, policy version, and conflict reasons.
- [ ] Add bounded `limit`/`offset` and enum filters as query parameters.
- [ ] Map unknown incident snapshots to `incident_not_found` with HTTP 404 and the existing request-ID error envelope.
- [ ] Document snapshot-ID volatility in endpoint descriptions and schema descriptions.
- [ ] Ensure conflict responses contain `priority: null` and never emit `review_required` as an operational priority level.

### Task 3: Prove the contract and regression boundary

**Files:**
- Create: `tests/contract/test_incident_read_api.py`
- Modify: `tests/contract/test_api_boundary.py`

**Interfaces:**
- Consumes: the real FastAPI application with an injected fake query service and the existing health dependency override.
- Produces: deterministic coverage for empty lists, filters, counts, ordering, detail evidence, conflicts, 404s, validation bounds, UTC serialization, strict DTOs, OpenAPI operation IDs, and unchanged health behavior.

- [ ] Write failing tests before production edits for the list/detail contract and error cases.
- [ ] Run the focused contract tests and confirm failures are caused by missing Task 7.2 behavior.
- [ ] Implement only the minimum production code required to make those tests pass.
- [ ] Run focused tests again, then the full pytest, Pyright, Ruff on API files, and deterministic OpenAPI checks.

## Self-review checklist

- Confirmed and pending counts are distinct in both list and detail responses.
- Category and priority filters operate on the query-service read model rather than route-local business logic.
- Conflict priority is `null` and conflict reasons are preserved.
- Empty storage returns `items=[]`, not 404.
- No submission, review resolution, mutation, database initialization, or embedding-model loading was added.
