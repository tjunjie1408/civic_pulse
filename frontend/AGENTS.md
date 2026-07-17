# Frontend Agent Rules

These rules apply to every file under `frontend/`.
The approved product and UX contract is
`docs/superpowers/specs/2026-07-16-civicpulse-vue-photo-map-design.md`.
Read it before changing frontend behavior, map semantics, or API contracts.

The repository-root instructions and domain invariants still apply here.
Only root-level Python formatting and naming conventions are replaced by the Vue and TypeScript
conventions below. Submission discipline, uncertainty boundaries, verification requirements, and
the prohibition on inventing domain behavior remain in force.

## Requirement language

- **MUST** marks a domain invariant, safety boundary, dependency rule, or required verification.
- **SHOULD** marks the default implementation approach; deviate only with a documented reason.
- **MAY** marks an optional technique or library, not an architectural commitment.

## MUST

- Use Vue 3 Composition API, `<script setup lang="ts">`, and strict TypeScript.
- Keep source dependencies directed from UI to application to domain/ports.
- Put API and MapLibre integrations behind adapters that implement domain/application ports.
- Wire concrete adapters only in a composition root; domain and application code must not import
  Vue, MapLibre, HTTP clients, generated DTO modules, or browser storage.
- Never recompute matching, clustering, operational priority, or API incident ordering in the
  browser. Display the API result and its explicit uncertainty state.
- Never introduce a numeric priority score unless it becomes part of the approved API contract.
- Keep pending-review evidence separate from confirmed incident membership, priority, and heat
  aggregation, as specified by the approved design.
- Preserve snapshot transitions as collections of previous and current IDs. Do not reduce a
  split, merge, or replacement to one `previous/current` pair.
- Give each mutable state concern one owner. Derived views may read or project state but must not
  create a second writable source of truth.
- Keep the imperative MapLibre map instance, sources, layers, controls, and subscriptions out of
  ordinary reactive stores and global application state. Own and dispose them at the adapter or
  map-host lifecycle boundary.
- Components must not issue raw `fetch` calls or construct API URLs. Use an application port.
- Treat OpenAPI as the remote contract. Add a DTO adapter only when transport and domain semantics
  differ; do not create one-to-one mapping layers that add no boundary value.
- Preserve complaint draft text and retry state when a photo upload fails. A failed photo must not
  hide, delete, or roll back a successfully saved complaint.
- Keep map category, severity, affected-area, dominant-category, and fallback behavior aligned
  with the approved design rather than renderer defaults or response iteration order.
- Organize product code feature-first. Move code to `shared` only after real reuse exists and its
  semantics are genuinely feature-independent.
- Keep component props, emits, composables, ports, adapters, and async results explicitly typed.
  Avoid `any`; isolate and justify unavoidable unsafe boundaries.
- Validate external data at a deliberate boundary when compile-time types cannot establish runtime
  safety. Do not mistake a TypeScript assertion for validation.
- Expose package scripts for type checking, linting, unit tests, and production builds. The chosen
  package manager must be able to run each gate non-interactively.
- Before reporting completion, run the relevant package scripts and any affected browser or
  contract tests. Report exact commands and results.
- Keep changes focused. Do not bundle a state-library migration, design-system rewrite, or broad
  directory refactor into an unrelated feature slice.

## SHOULD

- Build work as runnable vertical slices that cross UI, application, ports, and adapters while
  remaining independently testable and reversible.
- Write a failing focused test before implementing changed behavior, then keep the smallest useful
  regression test with the slice.
- Model complex remote or upload flows with typed async states that make idle, loading, success,
  empty, stale, retryable failure, and terminal failure explicit where applicable.
- Keep adapters focused: one transport or imperative integration concern per adapter, with tests at
  the boundary where behavior can drift.
- Keep Vue components presentation-oriented and move orchestration into application-facing
  composables or controllers.
- Prefer semantic names from the civic incident domain over generic names such as `data`, `item`,
  `manager`, or `helper`.
- Test observable behavior and contracts instead of Vue implementation details or private methods.
- Add negative tests for uncertainty, conflict priority, snapshot splits/merges, failed uploads,
  stale responses, and unavailable map resources when the slice touches those paths.
- Preserve a usable last-known incident view when a recoverable refresh or base-map request fails.
- Document a dependency-rule exception beside the narrowest affected boundary and include a removal
  condition.

## MAY

- Use Pinia when shared mutable client state has demonstrated that need.
- Use a query library when cache ownership, invalidation, or request deduplication warrants it.
- Use Vue Router for durable navigation such as `/incidents/:snapshotId`.
- Use a runtime validation library at untrusted boundaries.
- Use a virtual-list library after incident-count measurements justify the dependency.
- Choose the package manager, test runner, HTTP client, and directory details during implementation,
  provided all MUST rules and repository release gates remain satisfied.

Optional tools are not defaults. Do not add them pre-emptively or encode their APIs into domain and
application layers.
