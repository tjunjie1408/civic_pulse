# CivicPulse Vue Slice 4 Incident Detail Implementation Plan

## Goal

Deliver the next spec slice: a bounded, API-owned incident evidence preview in the queue and
an explicit `/incidents/:snapshotId` detail route that handles missing or stale membership
without guessing a successor snapshot.

## Guardrails

- Keep incident membership, matching, clustering, priority, and ordering server-owned.
- Expose complaint summaries, never `photo_path` or arbitrary server filesystem paths.
- Preserve the membership-derived snapshot ID and all many-to-many transition ID collections.
- Keep previews bounded with explicit `total` and `has_more` metadata.
- Preserve the current map/lifecycle and queue selection behavior.
- Preserve unrelated user files, including `CLAUDE.md` and the July 17 rebuild plan.

## Tasks

### 1. Define the bounded evidence contract

- [x] Add strict response models for confirmed complaint summaries and a bounded preview envelope.
- [x] Include text, category, coordinates, report time, and a safe photo-availability signal only;
  do not expose internal paths.
- [x] Add the preview to `IncidentDetailResponse` while keeping existing IDs, edges, and review
  candidates intact.
- [x] Freeze the contract through backend tests and the OpenAPI snapshot.

### 2. Implement the backend detail read

- [x] Select only complaints belonging to the requested current incident snapshot.
- [x] Apply one explicit preview limit and preserve repository/API order for the selected evidence.
- [x] Return `total` and `has_more`; do not let the UI fetch an unbounded detail payload.
- [x] Keep 404 behavior explicit for missing snapshot IDs.

### 3. Add the frontend detail boundary and accordion

- [x] Add typed `IncidentDetail` evidence models and a runtime decoder for the new response.
- [x] Add a framework-free detail port/use case with loading, ready, missing, and recoverable error
  states.
- [x] Make the queue an exactly-one-open accordion while retaining API incident order.
- [x] Render bounded confirmed report summaries and evidence-unavailable text without inventing
  descriptions, addresses, photos, or permanent case IDs.

### 4. Add the native detail route

- [x] Add `/incidents/:snapshotId` navigation through the existing composition root without adding a
  router dependency.
- [x] Provide an `Open full incident` action from the expanded row.
- [x] On missing/stale detail, return to the queue with a clear membership-changed notice and never
  select an arbitrary successor.
- [x] Preserve all API-provided previous/current snapshot IDs when a later transition contract is
  available.

### 5. Verify

- [x] Run targeted backend contract tests, OpenAPI freeze, frontend tests, lint, typecheck, build,
  and the existing dashboard contract gates.
- [x] Browser-check expanded/collapsed rows, exactly-one-open behavior, detail navigation, missing
  snapshot handling, keyboard focus, narrow layout, and console health.
- [x] Run `git diff --check` and preserve unrelated working-tree files.
