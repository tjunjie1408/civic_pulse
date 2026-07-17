# CivicPulse Vue Slice 1 Incident Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a runnable Vue 3 shell that consumes the frozen OpenAPI incident-list contract, preserves the API's operational order, and presents loading, empty, ready, and recoverable-failure queue states without inventing unavailable incident data.

**Architecture:** Keep frontend domain models and pure policies in `domain/`, use cases and outbound port interfaces in `application/`, concrete OpenAPI/HTTP work in `adapters/`, Vue state and rendering in `ui/`, and concrete wiring in `composition/`. Generate transport types from the frozen OpenAPI snapshot, validate the one consumed response at runtime, and map it once into camel-cased frontend models. The Vue UI invokes a framework-free `LoadIncidentQueue` use case; no domain or application file imports Vue, generated DTOs, or browser APIs.

**Tech Stack:** Vue 3 Composition API, strict TypeScript, Vite, pnpm 11.9.0, native `fetch`, `openapi-typescript`, ESLint flat config, Vitest, Vue Test Utils, jsdom, and `vue-tsc`.

## Global Constraints

- Treat `docs/superpowers/specs/2026-07-16-civicpulse-vue-photo-map-design.md` and `frontend/AGENTS.md` as the governing contracts. Preserve their MUST / SHOULD / MAY strength.
- Keep the dependency direction explicit: `ui -> application -> domain`; `adapters -> application/domain`; `composition -> ui/application/adapters`.
- Application owns the `IncidentListPort`; the HTTP adapter implements it. Ports do not belong in `domain/` merely to make the directory diagram symmetrical.
- Preserve the API `items` order byte-for-byte at the collection level. Do not call `sort`, infer a score, or choose a primary category from `category_summary[0]`.
- Model only `critical | high | medium | low` as operational priority. Render `priority: null` as “No operational priority”; never coerce it to `low` or `review_required`.
- Keep confirmed and pending counts separate. Pending evidence does not contribute to operational priority, confirmed membership, or later heat aggregation.
- Validate `unknown` JSON at the HTTP boundary. Generated TypeScript declarations are compile-time evidence, not runtime validation.
- Keep the last valid page visible when a refresh fails. Initial failure, empty success, and stale-data failure are distinct states.
- Do not invent description, address, photo, primary category, permanent case ID, or successor information: the list contract does not provide them.
- Use the Vite same-origin development proxy for `/api`; do not add backend CORS policy in this slice.
- Do not add Pinia, TanStack Query, Vue Router, MapLibre, Axios, Zod, a virtual-list library, a design-system package, or a generic repository-wide `shared` layer.
- Do not create map placeholders, map adapters, photo UI, detail routes, filters, pagination controls, or snapshot-transition behavior. They belong to later slices.
- Submit `frontend/pnpm-lock.yaml`. The first dependency install requires explicit network approval; all subsequent verification uses `--frozen-lockfile`.
- Preserve unrelated working-tree changes. Per the user's explicit instruction, do not stage or
  commit `frontend/AGENTS.md`, the repository `AGENTS.md`, or any `.agents/skills/**` file. Stage
  and commit only the implementation files named in this plan.

## Frozen Slice 1 Contract

The consumed operation is `GET /api/v1/incidents?limit=100&offset=0` (`operationId: incidentsList`). The server owns this order:

```text
critical -> high -> medium -> low -> no operational priority
latest_reported_at DESC
incident_id ASC
```

The frontend page model is intentionally smaller than the transport graph:

```ts
export type IncidentStatus = "confirmed" | "isolated" | "conflict"
export type IncidentCategory =
  | "pothole"
  | "blocked_drain"
  | "flooding"
  | "rubbish"
  | "street_light"
  | "other"
export type OperationalPriorityLevel = "critical" | "high" | "medium" | "low"

export interface OperationalPriority {
  readonly level: OperationalPriorityLevel
  readonly reasons: readonly string[]
  readonly policyVersion: string
}

export interface IncidentSummary {
  readonly incidentId: string
  readonly status: IncidentStatus
  readonly categories: readonly IncidentCategory[]
  readonly priority: OperationalPriority | null
  readonly confirmedReportCount: number
  readonly pendingCandidateCount: number
  readonly centroid: Readonly<{ latitude: number; longitude: number }>
  readonly radiusMetres: number
  readonly earliestReportedAt: string
  readonly latestReportedAt: string
  readonly conflictReasons: readonly string[]
}

export interface IncidentPage {
  readonly items: readonly IncidentSummary[]
  readonly limit: number
  readonly offset: number
  readonly total: number
}
```

Async failures and view state remain explicit:

```ts
export type IncidentListError =
  | { readonly kind: "network" }
  | { readonly kind: "service"; readonly status: number }
  | { readonly kind: "contract" }
  | { readonly kind: "aborted" }

export type IncidentListResult =
  | { readonly ok: true; readonly page: IncidentPage }
  | { readonly ok: false; readonly error: IncidentListError }

export type IncidentQueueState =
  | { readonly kind: "loading"; readonly previous: IncidentPage | null }
  | { readonly kind: "ready"; readonly page: IncidentPage }
  | { readonly kind: "empty"; readonly page: IncidentPage }
  | {
      readonly kind: "failed"
      readonly previous: IncidentPage | null
      readonly error: Exclude<IncidentListError, { kind: "aborted" }>
    }
```

## File Map

```text
frontend/
  package.json
  pnpm-lock.yaml
  index.html
  vite.config.ts
  eslint.config.js
  tsconfig.json
  tsconfig.app.json
  tsconfig.node.json
  src/
    env.d.ts
    main.ts
    App.vue
    App.spec.ts
    composition/create-app-services.ts
    features/incidents/
      domain/incident.ts
      application/incident-list-port.ts
      application/load-incident-queue.ts
      application/load-incident-queue.spec.ts
      adapters/http/generated/openapi.d.ts
      adapters/http/decode-incident-list.ts
      adapters/http/decode-incident-list.spec.ts
      adapters/http/incident-list-http-adapter.ts
      adapters/http/incident-list-http-adapter.spec.ts
      testing/incident-fixtures.ts
      ui/use-incident-queue.ts
      ui/use-incident-queue.spec.ts
      ui/IncidentQueuePage.vue
      ui/IncidentQueuePage.spec.ts
      ui/IncidentQueueRow.vue
      ui/IncidentQueueRow.spec.ts
    styles/tokens.css
    styles/base.css
```

Root files changed by Slice 1 are limited to `.gitignore`, `README.md`, and one strengthened API-order test in `tests/contract/test_incident_read_api.py`. Do not add a CI provider or modify `.pre-commit-config.yaml` in this slice; the repository has no established JS CI runtime, while non-interactive package scripts already provide the machine gates.

---

### Task 1: Bootstrap the non-interactive Vue and TypeScript toolchain

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/pnpm-lock.yaml`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/eslint.config.js`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/src/env.d.ts`
- Create: `frontend/src/App.spec.ts`
- Create: `frontend/src/App.vue`

- [ ] Create `package.json` with `private: true`, `type: "module"`, `packageManager: "pnpm@11.9.0"`, `engines.node: ">=22.12.0"`, and these non-interactive scripts:

  ```json
  {
    "dev": "vite",
    "api:generate": "openapi-typescript ../tests/contracts/openapi-v1.json -o src/features/incidents/adapters/http/generated/openapi.d.ts --immutable --alphabetize",
    "api:check": "openapi-typescript ../tests/contracts/openapi-v1.json -o src/features/incidents/adapters/http/generated/openapi.d.ts --immutable --alphabetize --check",
    "lint": "eslint . --max-warnings=0",
    "typecheck": "vue-tsc -b",
    "test": "vitest run",
    "test:watch": "vitest",
    "build": "vue-tsc -b && vite build",
    "check": "pnpm run api:check && pnpm run lint && pnpm run test && pnpm run build"
  }
  ```

- [ ] With network approval, install the dependency set with these exact commands; commit the
  resulting resolution in `pnpm-lock.yaml` rather than guessing patch versions in advance:

  ```powershell
  pnpm --dir frontend add vue
  pnpm --dir frontend add --save-dev vite @vitejs/plugin-vue typescript vue-tsc eslint @eslint/js eslint-plugin-vue typescript-eslint globals vitest @vue/test-utils jsdom openapi-typescript
  ```
- [ ] Configure strict project references, Vue SFC typing, jsdom tests, and Vite's Vue plugin. Keep Vitest configuration in `vite.config.ts`; do not create a second config unless the tools demonstrate a conflict.
- [ ] Configure ESLint flat config with TypeScript-aware Vue rules and `no-restricted-imports` overrides that reject:
  - `domain/**` imports from Vue, application, adapters, UI, composition, or generated DTOs;
  - `application/**` imports from Vue, adapters, UI, composition, generated DTOs, or browser storage;
  - `ui/**` imports directly from concrete adapters;
  - any `any` that is not explicitly isolated and justified.
- [ ] Write `App.spec.ts` first. Assert that the shell has a banner, the product name “CivicPulse”, an `h1` named “Incident operations”, and a main landmark. Run `pnpm --dir frontend test -- App.spec.ts` and confirm it fails because the shell is absent.
- [ ] Add the smallest semantic `App.vue` that satisfies the shell test; do not add queue, map, navigation, cards, or placeholder content yet.
- [ ] Run `pnpm --dir frontend run lint`, `pnpm --dir frontend run typecheck`, and `pnpm --dir frontend test -- App.spec.ts`; confirm all pass.
- [ ] Commit: `chore(frontend): bootstrap Vue toolchain`.

### Task 2: Generate the OpenAPI type boundary and strengthen API order evidence

**Files:**
- Create: `frontend/src/features/incidents/adapters/http/generated/openapi.d.ts`
- Modify: `tests/contract/test_incident_read_api.py`

- [ ] Run `pnpm --dir frontend run api:check` before generation and confirm it fails because the generated declaration is missing.
- [ ] Run `pnpm --dir frontend run api:generate`, then rerun `pnpm --dir frontend run api:check`; confirm the checked-in declaration is identical to `tests/contracts/openapi-v1.json`.
- [ ] Add a focused Python contract test named `test_list_incidents_orders_by_priority_then_recency_then_snapshot_id`. Build incidents whose fixtures isolate all three comparisons and assert the exact returned ID sequence:
  1. higher operational priority wins even when older;
  2. within one priority band, newer `latest_reported_at` wins;
  3. with equal priority and timestamp, `incident_id` string ascending is the stable tie-breaker;
  4. conflict / `priority: null` follows `low`.
- [ ] Run `uv run --offline python -m pytest tests/contract/test_incident_read_api.py -q`; confirm the new test passes against the existing server behavior without modifying production Python.
- [ ] Run `uv run --offline python -m pytest tests/contract/test_openapi_freeze.py -q`; confirm OpenAPI remains unchanged.
- [ ] Commit: `test: freeze incident queue ordering`.

### Task 3: Decode the incident-list response into frontend domain models

**Files:**
- Create: `frontend/src/features/incidents/domain/incident.ts`
- Create: `frontend/src/features/incidents/testing/incident-fixtures.ts`
- Create: `frontend/src/features/incidents/adapters/http/decode-incident-list.spec.ts`
- Create: `frontend/src/features/incidents/adapters/http/decode-incident-list.ts`

- [ ] Define the immutable domain types exactly as frozen above. Keep timestamps as ISO strings in Slice 1; formatting belongs to a presentation function, and no timezone conversion belongs in the adapter.
- [ ] In `incident-fixtures.ts`, create one valid transport fixture and one domain fixture with two deliberately reversed IDs. Reuse these typed fixtures in later tests instead of importing Python test helpers.
- [ ] Write decoder tests first for:
  - snake_case to camelCase mapping;
  - preservation of the incoming `items` and `category_summary` sequence;
  - `priority: null` remaining `null`;
  - all four operational priority levels;
  - rejection of `review_required` in an incident summary;
  - rejection of missing fields, extra fields, invalid UUID/date strings, non-finite coordinates/radius, and a malformed page envelope.
- [ ] Run `pnpm --dir frontend test -- decode-incident-list.spec.ts` and confirm the suite fails because the decoder is absent.
- [ ] Implement `decodeIncidentList(value: unknown): IncidentPage` with small local predicates. Import the generated `components["schemas"]["IncidentListResponse"]` only as a type-level cross-check inside the adapter directory; do not cast `unknown` to that type and call it validation.
- [ ] Preserve collection order with `map` only. Search this adapter for `.sort(` and confirm there are no hits.
- [ ] Run the focused decoder test, `pnpm --dir frontend run typecheck`, and `pnpm --dir frontend run lint`; confirm all pass.
- [ ] Commit: `feat(frontend): decode incident list contract`.

### Task 4: Define the application-owned port and queue use case

**Files:**
- Create: `frontend/src/features/incidents/application/incident-list-port.ts`
- Create: `frontend/src/features/incidents/application/load-incident-queue.spec.ts`
- Create: `frontend/src/features/incidents/application/load-incident-queue.ts`

- [ ] Define the port and result types without Vue, `fetch`, URL strings, or generated DTO imports:

  ```ts
  export interface IncidentListQuery {
    readonly limit: number
    readonly offset: number
  }

  export interface IncidentListPort {
    list(query: IncidentListQuery, signal: AbortSignal): Promise<IncidentListResult>
  }
  ```

- [ ] Write use-case tests first with a fake port. Assert `LoadIncidentQueue.execute(signal)` calls the port exactly once with `{ limit: 100, offset: 0 }`, forwards the same signal, and returns the port's item sequence unchanged.
- [ ] Run `pnpm --dir frontend test -- load-incident-queue.spec.ts` and confirm it fails because the use case is absent.
- [ ] Implement the smallest `LoadIncidentQueue` class. It fixes only the initial page size/offset and delegates transport behavior; it must not sort, cache, retry, or own Vue state.
- [ ] Run the focused test and ESLint dependency checks. Confirm `application/**` imports only its own files and `domain/**`.
- [ ] Commit: `feat(frontend): add incident queue use case`.

### Task 5: Implement the native-fetch HTTP adapter

**Files:**
- Create: `frontend/src/features/incidents/adapters/http/incident-list-http-adapter.spec.ts`
- Create: `frontend/src/features/incidents/adapters/http/incident-list-http-adapter.ts`

- [ ] Write adapter tests first with an injected `fetch` implementation. Cover:
  - `GET {baseUrl}/incidents?limit=100&offset=0` with the caller's abort signal;
  - valid 200 JSON decoded into the domain page without reordering;
  - network rejection -> `{ kind: "network" }`;
  - an `AbortError` -> `{ kind: "aborted" }`;
  - non-2xx -> `{ kind: "service", status }` without exposing server detail text;
  - invalid JSON or invalid 200 shape -> `{ kind: "contract" }`.
- [ ] Run `pnpm --dir frontend test -- incident-list-http-adapter.spec.ts` and confirm it fails because the adapter is absent.
- [ ] Implement `IncidentListHttpAdapter implements IncidentListPort`. Its constructor accepts `{ baseUrl, fetch }`; production composition passes `/api/v1` and `window.fetch.bind(window)`.
- [ ] Do not model 500/503 response bodies as a generated operation result: the frozen operation currently documents 200/422 while runtime can also return 500/503. Classify every non-2xx defensively by status and keep that OpenAPI documentation gap explicit; do not silently change the backend contract in this frontend slice.
- [ ] Run the focused adapter tests, typecheck, and lint; confirm all pass.
- [ ] Commit: `feat(frontend): add incident list HTTP adapter`.

### Task 6: Own request lifecycle in one Vue UI composable

**Files:**
- Create: `frontend/src/features/incidents/ui/use-incident-queue.spec.ts`
- Create: `frontend/src/features/incidents/ui/use-incident-queue.ts`

- [ ] Write composable tests first using a controllable fake `LoadIncidentQueue`. Cover:
  - initial `loading -> ready`;
  - 200 with zero items -> `empty`;
  - initial recoverable failure -> `failed` with no previous page;
  - ready page -> refresh loading with previous page -> failure retaining that page;
  - retry success replacing the page in API order;
  - a newer request aborting/invalidating an older request so a late response cannot overwrite current state;
  - scope disposal aborting the active request without surfacing a user-visible failure.
- [ ] Run `pnpm --dir frontend test -- use-incident-queue.spec.ts` and confirm it fails because the composable is absent.
- [ ] Implement `useIncidentQueue(loadIncidentQueue)` as the sole owner of queue request state. Expose readonly `state`, `load()`, `refresh()`, and `retry()`; do not expose a second writable item list.
- [ ] Store the previous valid `IncidentPage` inside loading/failed states. Do not convert failure into an empty page and do not add automatic retries or backoff in Slice 1.
- [ ] Run the focused test, typecheck, and lint; confirm all pass.
- [ ] Commit: `feat(frontend): model incident queue lifecycle`.

### Task 7: Render the accessible, API-ordered incident queue

**Files:**
- Create: `frontend/src/features/incidents/ui/IncidentQueueRow.spec.ts`
- Create: `frontend/src/features/incidents/ui/IncidentQueueRow.vue`
- Create: `frontend/src/features/incidents/ui/IncidentQueuePage.spec.ts`
- Create: `frontend/src/features/incidents/ui/IncidentQueuePage.vue`

- [ ] Write `IncidentQueueRow` tests first. Assert it displays all category labels without selecting a primary category, the four operational priority labels, “No operational priority” for `null`, confirmed and pending counts as separate facts, radius, latest update, and an abbreviated snapshot ID only as secondary metadata.
- [ ] Confirm the row test fails, then implement a semantic `<li><article>` row. Do not render badges for every field, fake location text, description, photo, or a details link.
- [ ] Write `IncidentQueuePage` tests first for:
  - an initial `aria-busy` loading skeleton with no false empty message;
  - a clear empty success state;
  - an initial failure with one retry action;
  - ready rows in the exact page order;
  - stale rows remaining visible under a refresh-failure notice;
  - retry emitting/calling exactly once;
  - `total > items.length` displaying “Showing 100 of N” without inventing pagination controls.
- [ ] Confirm the page test fails, then implement the page around `useIncidentQueue`. Use a real list landmark and headings that describe the available data, such as “Flooding · blocked drain”, not a fabricated incident title.
- [ ] Run both component tests, then the full Vitest suite, typecheck, and lint.
- [ ] Commit: `feat(frontend): render operational incident queue`.

### Task 8: Wire the composition root and apply the restrained government visual system

**Files:**
- Create: `frontend/src/composition/create-app-services.ts`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/base.css`
- Modify: `frontend/index.html`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.spec.ts`
- Modify: `frontend/vite.config.ts`

- [ ] Add an App integration test using an injected fake `LoadIncidentQueue`; assert the shell renders queue states without importing the HTTP adapter into a component test.
- [ ] In `create-app-services.ts`, construct `IncidentListHttpAdapter`, then `LoadIncidentQueue`. This is the only production file that knows both concrete adapter and use case.
- [ ] In `main.ts`, create the services once and pass the use case into `App`; `App` passes it to `IncidentQueuePage`. Do not use provide/inject or a global store for this single dependency.
- [ ] Configure the Vite development proxy from `/api` to `http://127.0.0.1:8000`, preserving the `/api/v1` path. Production keeps a same-origin `/api/v1` base URL.
- [ ] Ensure `frontend/index.html` loads `/src/main.ts` with a module script so the built page actually boots the composition root; verify the generated `dist/index.html` contains that entry.
- [ ] Implement the approved serious, cold, white-first visual direction:
  - white primary surface, cool gray canvas and 1px dividers;
  - near-black text and readable `"Segoe UI", Arial, sans-serif` without a remote font request;
  - one restrained blue for focus/actions and one muted red reserved for critical/error emphasis;
  - grayscale hierarchy for high/medium/low priority rather than four decorative colors;
  - no gradients, glass effects, oversized rounded cards, floating dashboard tiles, ornamental shadows, or pill-heavy metadata;
  - 15–16px body text, at least 1.45 line-height, visible keyboard focus, and a queue width that remains readable from 1024px upward.
- [ ] Use typography, spacing, divider rhythm, hover/focus transitions, and a subtle row reveal for hierarchy. Respect `prefers-reduced-motion`; do not animate layout or delay access to data.
- [ ] Run App/component tests, typecheck, lint, and build.
- [ ] Commit: `feat(frontend): wire incident operations shell`.

### Task 9: Document and run the Slice 1 release gates

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`

- [ ] Add only `frontend/node_modules/`, `frontend/dist/`, and `frontend/coverage/` to `.gitignore`.
- [ ] Document:
  - required Node `>=22.12.0` and pnpm `11.9.0`;
  - `pnpm --dir frontend install --frozen-lockfile`;
  - the API server command;
  - `pnpm --dir frontend run dev -- --host 127.0.0.1`;
  - each frontend gate and the combined `check` command.
- [ ] Search the frontend for prohibited dependencies and behaviors:

  ```powershell
  rg -n "pinia|@tanstack|maplibre|vue-router|axios|zod|\.sort\(" frontend/src frontend/package.json
  rg -n "TODO|TBD|placeholder|lorem|coming soon" frontend/src
  ```

  Expected result: no production dependency hit, no queue sorting hit, and no user-visible placeholder copy.
- [ ] Run the exact frontend gates from a clean dependency install:

  ```powershell
  pnpm --dir frontend install --frozen-lockfile
  pnpm --dir frontend run api:check
  pnpm --dir frontend run lint
  pnpm --dir frontend run typecheck
  pnpm --dir frontend run test
  pnpm --dir frontend run build
  pnpm --dir frontend run check
  ```

- [ ] Run the affected backend contract gates:

  ```powershell
  uv run --offline python -m pytest tests/contract/test_incident_read_api.py tests/contract/test_openapi_freeze.py tests/contract/test_dashboard_gateway.py tests/contract/test_dashboard_recovery.py -q
  ```

- [ ] Start the API and Vite processes in separate terminals:

  ```powershell
  uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000
  pnpm --dir frontend run dev -- --host 127.0.0.1
  ```

- [ ] Using the in-app browser, verify at 1440x900 and 1024x768: first load, empty state, retryable failure, stale-data failure, keyboard focus, exact queue order, text contrast, no horizontal clipping, and reduced-motion behavior. Capture evidence only after the rendered page matches the white-first neutral government direction.
- [ ] Run `git diff --check` and `git status --short`. Confirm no generated database, model cache, `node_modules`, `dist`, coverage, or unrelated user file is staged.
- [ ] Review the diff against every Global Constraint, then commit only the Slice 1 documentation/gate changes as `docs: add Vue frontend workflow`.

## Completion Evidence

Slice 1 is complete only when the handoff includes:

```text
OpenAPI drift:       pnpm --dir frontend run api:check        PASS
Dependency rules:    pnpm --dir frontend run lint             PASS
Strict types:        pnpm --dir frontend run typecheck         PASS
Behavior tests:      pnpm --dir frontend run test              PASS
Production bundle:   pnpm --dir frontend run build             PASS
Combined frontend:   pnpm --dir frontend run check             PASS
Python contracts:    targeted pytest command                   PASS
Rendered UI:         desktop browser evidence                  PASS
Scope audit:         prohibited-pattern search + git status    PASS
```

Any failed gate remains a failure. Do not describe a partial run, a skipped network install, or an unverified browser state as complete.
