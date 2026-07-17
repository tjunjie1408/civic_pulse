# Task 7.3 Mutation API Implementation Plan

> **For agentic workers:** Use test-first implementation and stop at the Task 7.3 evidence gate.

**Goal:** Expose complaint submission and protected deterministic reset APIs while preserving service orchestration, idempotency, transaction, and snapshot semantics.

**Architecture:** Persist an idempotency request fingerprint and the original submission result beside the submission key. Routes validate and map DTOs only; `CivicPulseService.submit_complaint()` and `reset_seed()` remain the mutation boundaries. Admin reset uses server-side settings and is disabled by default.

## Scope

- `POST /api/v1/complaints`
- `POST /api/v1/admin/reset`
- Strict mutation DTOs, stable errors, snapshot transition response, and contract tests.

## Global constraints

- Same idempotency key plus same normalized request replays with `created=false`.
- Same key plus different normalized request returns `409 idempotency_conflict`.
- Routes never access repositories or run normalization, embeddings, matching, clustering, or priority logic.
- Reset never accepts a client filesystem path or URL and is disabled by default.
- Mutation and reset failures must not leave partial persistent state.
- Incident IDs remain membership-derived snapshot IDs.

## Tasks

### Task 1: Red tests

- Add submission contract tests for header bounds, success, replay, conflict, validation, transition metadata, pending/conflict results, and service error envelopes.
- Add reset tests for disabled mode, server-side path usage, deterministic summary, reset failure, health regression, and OpenAPI stability.
- Update the service integration expectation so same-key different-payload requests are rejected.
- Run focused tests and confirm expected failures before production edits.

### Task 2: Persistence and service semantics

- Add request fingerprint and stored result payload columns with backward-compatible schema migration.
- Store and retrieve the original `SubmissionResult` for restart-safe replay.
- Add normalized fingerprint comparison and an explicit idempotency conflict error.
- Extend submission/reset results with transition and summary data without moving business logic into routes.

### Task 3: API boundary

- Add strict submission, transition, relationship, and reset response DTOs.
- Add the two routes, settings/dependencies, and stable error mappings.
- Keep reset configuration server-side and disabled by default.

### Task 4: Verification

- Run focused red/green tests, full pytest, Pyright, API Ruff, `git diff --check`, and deterministic OpenAPI checks.
- Stop at the Task 7.3 evidence gate; do not add review resolution, upload, authentication framework, or background-task endpoints.
