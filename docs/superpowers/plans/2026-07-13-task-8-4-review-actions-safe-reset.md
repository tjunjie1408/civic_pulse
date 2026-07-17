# Task 8.4 Review Actions and Safe Demo Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Dashboard business loop by resolving reviews through the frozen HTTP API and restoring the deterministic demo seed through an explicit, protected reset flow.

**Architecture:** Extend the typed Dashboard gateway with strict request/response models for review resolution and seed reset. Keep all server truth in the API; session state stores only selection, draft, transition metadata, and resettable UI state. A shared transition method handles previous/new incident snapshot IDs for both approve and reject.

**Tech Stack:** Python 3.12, Pydantic v2, httpx, Streamlit, pytest, Pyright, Ruff.

## Global Constraints

- Dashboard code must use only the frozen HTTP API and must not import backend service, repository, SQLite, or domain models.
- `AUTO_MATCH` may form confirmed incidents; `REVIEW_REQUIRED` remains candidate evidence only; priority uses confirmed evidence only.
- Incident IDs are membership-derived snapshot identifiers, so every mutation must use API-provided previous/new snapshot IDs.
- Review matcher evidence remains immutable read evidence; final officer decision is displayed separately.
- Reset sends no path or URL from the client and requires exact confirmation text `RESET DEMO`.
- Review actions require a non-empty reviewer ID and bounded note; stale conflicts are never auto-retried.

---

### Task 1: Add strict review mutation and reset gateway contracts

**Files:**
- Modify: `src/civicpulse_dashboard/api_models.py`
- Modify: `src/civicpulse_dashboard/api_client.py`
- Modify: `src/civicpulse_dashboard/api_errors.py`
- Test: `tests/contract/test_dashboard_review_mutations.py`

**Interfaces:**
- Produces `ReviewResolutionRequest`, `ReviewMutationResponse`, `SeedResetResponse`.
- Produces `ApiClient.approve_review(review_id, reviewer_id, note)`, `ApiClient.reject_review(review_id, reviewer_id, note)`, and `ApiClient.reset_demo()`.

- [ ] **Step 1: Write the failing contract tests** for strict response parsing, endpoint paths, JSON body, no reset request body, and `review_stale` mapping.
- [ ] **Step 2: Run the focused tests** and verify failure because the models and methods do not exist.
- [ ] **Step 3: Add the strict Pydantic models** matching the frozen OpenAPI fields, including nullable priorities and `extra="forbid"` inheritance.
- [ ] **Step 4: Add the three typed gateway methods** using POST, request validation, and the existing sanitized error conversion.
- [ ] **Step 5: Run the focused tests** and verify all pass.

### Task 2: Centralize transition and resettable session state

**Files:**
- Modify: `src/civicpulse_dashboard/state.py`
- Test: `tests/unit/test_dashboard_state.py`

**Interfaces:**
- Produces `DashboardSessionState.apply_review_transition(...)` for both approve and reject.
- Produces `DashboardSessionState.clear_after_reset()` that preserves API/user configuration but clears selections, drafts, idempotency, mutation metadata, and in-progress flags.

- [ ] **Step 1: Write failing state tests** for review transitions, stale-note preservation, and complete reset cleanup.
- [ ] **Step 2: Run the tests** and verify the new methods/fields are absent.
- [ ] **Step 3: Implement the shared transition metadata and reset cleanup** without storing incident/review payloads.
- [ ] **Step 4: Run the state tests and existing dashboard state tests** and verify all pass.

### Task 3: Implement review resolution UI

**Files:**
- Modify: `src/civicpulse_dashboard/ui/review_queue.py`
- Modify: `src/civicpulse_dashboard/app.py`
- Test: `tests/contract/test_dashboard_review_mutations.py`

**Interfaces:**
- Review detail continues to display original evidence and adds separate final decision fields.
- Pending review actions call only `ApiClient.approve_review` or `ApiClient.reject_review`.
- Error behavior: not found clears selection and reloads queue; already resolved reloads; stale preserves note and requires re-confirmation.

- [ ] **Step 1: Add pure UI decision/transition helpers and failing tests** for action labels, conflict presentation, stale handling, and no optimistic mutation.
- [ ] **Step 2: Run focused UI tests** and verify they fail.
- [ ] **Step 3: Add bounded reviewer/note controls, explicit approve/reject confirmation, disabled concurrent actions, and safe error handling.**
- [ ] **Step 4: Apply the shared API transition result and show conflict priority as unavailable.**
- [ ] **Step 5: Run focused dashboard tests** and verify all pass.

### Task 4: Implement protected deterministic reset UI

**Files:**
- Create: `src/civicpulse_dashboard/ui/safe_reset.py`
- Modify: `src/civicpulse_dashboard/app.py`
- Test: `tests/contract/test_dashboard_reset.py`

**Interfaces:**
- Produces `reset_enabled()` from Dashboard-only configuration.
- Produces `reset_confirmation_is_valid(value)` requiring exact `RESET DEMO`.
- `render_safe_reset(client, state)` calls `ApiClient.reset_demo()` only after Dashboard config and exact confirmation pass.

- [ ] **Step 1: Write failing tests** for hidden-by-default UI configuration, exact confirmation, no request on invalid confirmation, and reset summary parsing.
- [ ] **Step 2: Run focused tests** and verify failure.
- [ ] **Step 3: Implement the reset panel** with no path input, sanitized disabled/error display, state cleanup, and rerun-triggered reload.
- [ ] **Step 4: Add it to the app sidebar** without affecting API base URL or user configuration.
- [ ] **Step 5: Run focused tests and verify all pass.

### Task 5: Full verification and browser smoke

**Files:**
- Verify only; no production edits unless a test exposes a Task 8.4 defect.

- [ ] **Step 1: Run focused dashboard tests.**
- [ ] **Step 2: Run `uv run --offline python -m pytest -q`.**
- [ ] **Step 3: Run `uv run --offline pyright src scripts`.**
- [ ] **Step 4: Run `uv run --offline ruff check src/civicpulse_dashboard`.**
- [ ] **Step 5: Run `git diff --check` and inspect staged/untracked scope.**
- [ ] **Step 6: Start Streamlit with the API unavailable and verify only safe unavailable/readiness UI appears; if a test harness can exercise a live API, verify the review/reset paths do not bypass HTTP.**

### Task 6: Commit only after explicit user approval

- [ ] **Step 1: Report verification evidence and remaining warnings/uncertainty.**
- [ ] **Step 2: Wait for explicit commit instruction.**
- [ ] **Step 3: Stage only Task 8.4 files and commit with `feat(dashboard): add review actions and safe demo reset`.**
