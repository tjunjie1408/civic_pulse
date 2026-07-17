# CivicPulse Vue 3 Frontend Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the CivicPulse operator frontend as a Vue 3 + TypeScript single-page app with a white-neutral government design, a per-category colored incident heatmap (MapLibre GL), and accordion cards for incident and review records.

**Architecture:** A new `frontend/` Vite + Vue 3 + TypeScript SPA that is a pure HTTP client of the frozen `/api/v1` FastAPI contract. Types are generated from the frozen OpenAPI snapshot; all ranking, matching, clustering, and priority logic stays server-owned. The Vite dev server proxies `/api` to `127.0.0.1:8000` because the API has no CORS middleware. The existing Streamlit dashboard is left untouched until the Vue app reaches parity.

**Tech Stack:** Vue 3.5 (script setup), TypeScript strict, Vite 6, Pinia, vue-router, maplibre-gl, exifr (client-side EXIF GPS extraction for photo evidence), openapi-typescript (types generated from `tests/contracts/openapi-v1.json`), Vitest + @vue/test-utils + jsdom, @fontsource/public-sans + @fontsource/ibm-plex-mono (self-hosted fonts, offline-friendly).

## Design Read (declared per taste-skill Section 0.B)

*Reading this as: a public-sector operational console for municipal officers and first-time demo users, with a trust-first white-neutral government language, leaning toward a custom Vue 3 token system with Public Sans type and MapLibre GL for the category-colored incident map.*

Dials: `DESIGN_VARIANCE: 3`, `MOTION_INTENSITY: 2`, `VISUAL_DENSITY: 5` (public-sector preset). This is product UI, not a landing page, so the taste-skill's discipline rules apply (contrast locks, one accent, shape lock, no AI tells) but not its marketing-page composition rules.

### Design tokens (locked)

| Token | Value | Use |
| --- | --- | --- |
| `--surface-page` | `#fcfcfd` | Page background (near-white; pure `#fff` reserved for raised cards) |
| `--surface-raised` | `#ffffff` | Cards, panels |
| `--surface-sunken` | `#f4f6f8` | Filter bars, evidence blocks, table stripes |
| `--border` | `#d9dee3` | Hairlines, card borders |
| `--text-primary` | `#16191d` | Headings, body |
| `--text-secondary` | `#4b5560` | Labels, captions |
| `--accent` | `#0b5394` | The ONE interactive accent (links, buttons, focus, active tab) |
| `--accent-strong` | `#083b6b` | Button hover |

**Category encoding (Okabe-Ito derived, colorblind-safe; used identically in chips, accordion card left edges, map heat layers, and the legend):**

| Category | Hex |
| --- | --- |
| `pothole` | `#d55e00` |
| `blocked_drain` | `#56b4e9` |
| `flooding` | `#0072b2` |
| `rubbish` | `#009e73` |
| `street_light` | `#e69f00` |
| `other` | `#6e7781` |

Category color is data encoding, never text color: chips render a colored dot + `--text-primary` text so contrast always passes AA.

**Type:** Public Sans 400/500/600/700 for UI; IBM Plex Mono 400/500 for coordinates, metrics, IDs, and counts. Scale: 13 / 14 / 16 / 18 / 22 / 28 px.

**Shape lock:** 8px radius on cards and panels, 6px on buttons and inputs, pill radius only on chips/badges. Documented rule, applied everywhere.

**Theme lock:** Light only, by explicit user instruction ("white for neutral, government read"). No dark mode in v1.

**Motion:** Hover/active states plus one accordion expand/collapse transition (CSS `grid-template-rows`, 200ms), disabled under `prefers-reduced-motion`. Nothing else moves.

**Minimalism rule:** every element must serve an operator task; if it does not, it does not ship. No icon library (the only glyph is a CSS-drawn chevron on accordion triggers), no taglines, no decorative imagery, no ornament.

**Signature element:** the category color system as a single "civic ink" thread — the 3px colored left edge on every accordion card matches the chip dot, the map heat color, and the legend swatch, so first-time users learn one color language that works across list and map.

**Copy register:** plain operational English, sentence case, active voice. No em-dashes anywhere. Errors state what happened and what to do next. The synthetic-data notice stays visible in the shell footer.

## Global Constraints

- Backend is frozen: no changes under `src/civicpulse/` or to `tests/contracts/openapi-v1.json`. The SPA consumes `/api/v1` exactly as published.
- API access in dev goes through the Vite proxy (`/api` → `http://127.0.0.1:8000`); the client base URL is `/api/v1`. The API has no CORS middleware; do not add any.
- The frontend never recomputes ranking, matching, hotspot strength, or priority. It projects API responses only (same boundary the Streamlit client honors).
- Pending candidates never inflate confirmed counts or map intensity: the map plots only `status == "confirmed"` incidents, weighted by `confirmed_report_count`.
- TypeScript `strict: true`; `npm run typecheck` (vue-tsc) must pass at every commit.
- All tests via Vitest; every task follows test-first where a pure or behavioral unit exists.
- Node >= 20. All `npm` commands run inside `frontend/`.
- Zero em-dash characters in any user-visible string.
- WCAG AA contrast for all text and controls; visible keyboard focus (`:focus-visible` ring in `--accent`).
- Minimalism: no icon library and no hand-rolled SVG icons. The only glyph is the CSS-drawn chevron in AccordionCard; everything else is text.
- Photo evidence stays client-side in v1: the frozen contract has no upload endpoint, so the complaint carries `photo_path` (the sanitized file name) only, which the server's priority policy already counts as evidence. Server-side photo storage/processing requires a new multipart endpoint plus an OpenAPI snapshot update and is documented as follow-up, never built silently here.
- Heat coverage encodes severity: heatmap radius scales with the incident's priority level (critical > high > medium > low); heat weight stays driven by `confirmed_report_count` only.
- Fonts self-hosted via @fontsource packages (works offline after `npm install`); never a Google Fonts `<link>`.
- Map basemap uses CARTO light raster tiles (no API key). Tiles need network; the map component keeps a neutral `background` layer and all incident layers render even when tiles fail, matching the project's local-first posture.
- Demo map center: `[101.52, 3.07]` (Shah Alam-inspired synthetic district), zoom 12.
- Existing Streamlit dashboard stays untouched and runnable throughout.
- Commit after every task with the message given in the task.

## File Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts                  Vite + Vitest + /api proxy
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json (scaffolded)
├── src/
│   ├── main.ts                     App bootstrap, fonts, router, pinia
│   ├── App.vue                     Shell: header, nav tabs, readiness gate, footer notice
│   ├── router.ts                   4 routes: queue, map, submit, reviews
│   ├── styles/
│   │   ├── tokens.css              Design tokens (single source of visual truth)
│   │   └── base.css                Reset, typography, focus ring, shared primitives
│   ├── api/
│   │   ├── types.gen.ts            GENERATED by openapi-typescript (never hand-edited)
│   │   ├── types.ts                Friendly aliases over generated schemas
│   │   ├── errors.ts               ApiRequestError / ApiConnectivityError
│   │   ├── client.ts               Typed fetch gateway (the ONLY fetch call site)
│   │   └── index.ts                Singleton `api` instance
│   ├── domain/
│   │   ├── categories.ts           CATEGORY_META: labels + colors + heat ramps
│   │   ├── priority.ts             PRIORITY_META: labels + badge tints
│   │   └── format.ts               Date, coordinate, distance, percent formatting
│   ├── stores/
│   │   ├── health.ts               Readiness gate state
│   │   ├── incidents.ts            List + filters + per-incident detail cache
│   │   └── reviews.ts              Review list + detail + approve/reject
│   ├── components/
│   │   ├── AccordionCard.vue       Accessible disclosure card (shared)
│   │   ├── CategoryChip.vue        Dot + label
│   │   ├── PriorityBadge.vue       Tinted badge incl. "unavailable" state
│   │   ├── StatusBadge.vue         confirmed / isolated / conflict
│   │   ├── incidents/
│   │   │   ├── IncidentSummaryRow.vue
│   │   │   └── IncidentDetailPanel.vue
│   │   ├── map/
│   │   │   ├── IncidentMap.vue     MapLibre component (all map imperative code)
│   │   │   ├── geojson.ts          Pure incident → GeoJSON projection + severity ranking
│   │   │   └── MapLegend.vue       Category legend with layer toggles
│   │   ├── submit/
│   │   │   └── photo.ts            Pure photo validation + EXIF GPS extraction
│   │   └── reviews/
│   │       ├── ReviewSummaryRow.vue
│   │       └── ReviewEvidencePanel.vue
│   └── views/
│       ├── QueueView.vue           Operational queue (accordion cards + filters)
│       ├── MapView.vue             Heatmap page (severity-scaled coverage + priority filter)
│       ├── SubmitView.vue          Complaint submission form + photo evidence + outcome panel
│       └── ReviewsView.vue         Review queue (accordion cards + resolve forms)
└── src/**/*.test.ts                Vitest specs co-located with sources
```

**Non-goals for v1** (explicitly out of scope; revisit after parity): safe demo reset UI (server flag is disabled by default), map-click location picker on the submit form, dark mode, production static hosting story, deleting the Streamlit app, server-side photo upload/storage/analysis (needs a new multipart endpoint and an explicit OpenAPI snapshot update; the v1 photo interface is client-side evidence capture per Task 9).

---

### Task 1: Scaffold, tooling, and the design token system

**Files:**
- Create: `frontend/` via Vite scaffold (`index.html`, `vite.config.ts`, `tsconfig*.json`, `src/main.ts`, `src/App.vue`)
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/base.css`
- Test: `frontend/src/App.test.ts` (smoke)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: npm scripts `dev`, `build`, `test`, `typecheck`, `gen:api`; CSS custom properties consumed by every later component; `/api` dev proxy.

- [ ] **Step 1: Scaffold the project**

Run from the repository root:

```powershell
npm create vite@latest frontend -- --template vue-ts
cd frontend
npm install
npm install pinia vue-router maplibre-gl exifr @fontsource/public-sans @fontsource/ibm-plex-mono
npm install -D vitest @vue/test-utils jsdom openapi-typescript
```

- [ ] **Step 2: Replace `vite.config.ts` with proxy + test config**

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
  },
})
```

Add npm scripts in `package.json` (merge into the scaffolded `scripts` block):

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "typecheck": "vue-tsc --noEmit",
    "gen:api": "openapi-typescript ../tests/contracts/openapi-v1.json -o src/api/types.gen.ts"
  }
}
```

- [ ] **Step 3: Write `src/styles/tokens.css`**

```css
:root {
  /* Surfaces */
  --surface-page: #fcfcfd;
  --surface-raised: #ffffff;
  --surface-sunken: #f4f6f8;
  --border: #d9dee3;
  --border-strong: #aab3bc;

  /* Text */
  --text-primary: #16191d;
  --text-secondary: #4b5560;
  --text-muted: #6a7580;

  /* The single interactive accent */
  --accent: #0b5394;
  --accent-strong: #083b6b;
  --accent-tint: #e8f0f8;

  /* Category encoding (colorblind-safe) */
  --cat-pothole: #d55e00;
  --cat-blocked-drain: #56b4e9;
  --cat-flooding: #0072b2;
  --cat-rubbish: #009e73;
  --cat-street-light: #e69f00;
  --cat-other: #6e7781;

  /* Status */
  --status-confirmed-bg: #e3f2e9;
  --status-confirmed-text: #0a6b3d;
  --status-isolated-bg: #eef1f4;
  --status-isolated-text: #4b5560;
  --status-conflict-bg: #fdeaea;
  --status-conflict-text: #8e1f1f;

  /* Priority badge tints */
  --prio-critical-bg: #fde7e7;
  --prio-critical-text: #8e1f1f;
  --prio-high-bg: #ffe9d6;
  --prio-high-text: #8a3e10;
  --prio-medium-bg: #fff4c7;
  --prio-medium-text: #6b5000;
  --prio-low-bg: #eef1f4;
  --prio-low-text: #4b5560;
  --prio-none-bg: #f4f6f8;
  --prio-none-text: #57606a;

  /* Feedback */
  --error-bg: #fdeaea;
  --error-text: #8e1f1f;
  --error-border: #f2b8b5;

  /* Shape lock: 8px cards, 6px controls, pill chips */
  --radius-card: 8px;
  --radius-control: 6px;
  --radius-pill: 999px;

  /* Type */
  --font-ui: 'Public Sans', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, monospace;
}
```

- [ ] **Step 4: Write `src/styles/base.css`**

```css
*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--surface-page);
  color: var(--text-primary);
  font-family: var(--font-ui);
  font-size: 14px;
  line-height: 1.5;
}

h1, h2, h3, h4, p {
  margin: 0;
}

button {
  font: inherit;
  cursor: pointer;
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.mono {
  font-family: var(--font-mono);
  font-size: 13px;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

/* Shared control styles */
.control {
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  color: var(--text-primary);
  padding: 6px 10px;
  font: inherit;
}

.button-primary {
  background: var(--accent);
  color: #ffffff;
  border: 1px solid var(--accent);
  border-radius: var(--radius-control);
  padding: 8px 16px;
  font-weight: 600;
}

.button-primary:hover {
  background: var(--accent-strong);
}

.button-primary:active {
  transform: translateY(1px);
}

.button-primary:disabled {
  background: var(--border-strong);
  border-color: var(--border-strong);
  cursor: not-allowed;
}

.button-secondary {
  background: var(--surface-raised);
  color: var(--accent);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  padding: 8px 16px;
  font-weight: 600;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-weight: 600;
  font-size: 13px;
}

.field-help {
  color: var(--text-muted);
  font-size: 12px;
}

.field-error {
  color: var(--error-text);
  font-size: 12px;
}

.panel-error {
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  color: var(--error-text);
  border-radius: var(--radius-card);
  padding: 12px 16px;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Replace `src/main.ts` and strip scaffold demo files**

Delete `src/components/HelloWorld.vue`, `src/style.css`, and `src/assets/vue.svg` if present. Write `src/main.ts`:

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@fontsource/public-sans/400.css'
import '@fontsource/public-sans/500.css'
import '@fontsource/public-sans/600.css'
import '@fontsource/public-sans/700.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './styles/tokens.css'
import './styles/base.css'
import App from './App.vue'
import { router } from './router'

createApp(App).use(createPinia()).use(router).mount('#app')
```

Temporary `src/router.ts` so the app compiles before Task 4 (replaced there):

```ts
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: { template: '<p>CivicPulse frontend scaffold</p>' } },
  ],
})
```

Temporary `src/App.vue`:

```vue
<template>
  <main>
    <h1>CivicPulse operations</h1>
    <router-view />
  </main>
</template>
```

Set `<title>CivicPulse operations</title>` and `<html lang="en">` in `index.html`.

- [ ] **Step 6: Write the smoke test `src/App.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import App from './App.vue'

describe('App shell', () => {
  it('renders the product name', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }],
    })
    const wrapper = mount(App, { global: { plugins: [createPinia(), router] } })
    await router.isReady()
    expect(wrapper.text()).toContain('CivicPulse')
  })
})
```

- [ ] **Step 7: Verify**

Run: `npm run test -- --run` → expect 1 passed.
Run: `npm run typecheck` → expect 0 errors.
Run: `npm run dev` briefly and load `http://localhost:5173` → scaffold heading renders.

- [ ] **Step 8: Commit**

```powershell
git add frontend
git commit -m "feat(frontend): scaffold Vue 3 + TypeScript app with government design tokens"
```

---

### Task 2: Generated API types and the typed HTTP client

**Files:**
- Create (generated): `frontend/src/api/types.gen.ts`
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/errors.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/index.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: `tests/contracts/openapi-v1.json` (frozen snapshot, read-only)
- Produces: `api` singleton with methods `healthReady(): Promise<HealthResponse>`, `listIncidents(params?: IncidentListParams): Promise<IncidentListResponse>`, `getIncident(id: string): Promise<IncidentDetailResponse>`, `listReviews(params?: ReviewListParams): Promise<ReviewListResponse>`, `getReview(id: string): Promise<ReviewDetailResponse>`, `approveReview(id, body: ReviewResolutionRequest): Promise<ReviewMutationResponse>`, `rejectReview(id, body): Promise<ReviewMutationResponse>`, `submitComplaint(body: ComplaintCreateRequest, idempotencyKey: string): Promise<ComplaintSubmissionResponse>`; error classes `ApiRequestError` (has `code`, `userMessage`, `requestId`, `status`) and `ApiConnectivityError`.

- [ ] **Step 1: Generate types**

Run: `npm run gen:api`
Expected: `src/api/types.gen.ts` created. Open it and confirm `components['schemas']` contains `IncidentSummaryResponse`, `IncidentDetailResponse`, `IncidentListResponse`, `ReviewListResponse`, `ReviewDetailResponse`, `ReviewMutationResponse`, `ComplaintSubmissionResponse`, `HealthResponse`, `ApiErrorResponse`. If any name differs, adjust the aliases in Step 2 to the generated names; never edit the generated file.

- [ ] **Step 2: Write `src/api/types.ts`**

```ts
import type { components } from './types.gen'

type Schemas = components['schemas']

export type HealthResponse = Schemas['HealthResponse']
export type IncidentSummary = Schemas['IncidentSummaryResponse']
export type IncidentDetail = Schemas['IncidentDetailResponse']
export type IncidentListResponse = Schemas['IncidentListResponse']
export type ReviewSummary = Schemas['ReviewSummaryResponse']
export type ReviewDetail = Schemas['ReviewDetailResponse']
export type ReviewListResponse = Schemas['ReviewListResponse']
export type ReviewMutationResponse = Schemas['ReviewMutationResponse']
export type ReviewResolutionRequest = Schemas['ReviewResolutionRequest']
export type ComplaintCreateRequest = Schemas['ComplaintCreateRequest']
export type ComplaintSubmissionResponse = Schemas['ComplaintSubmissionResponse']
export type ApiErrorResponse = Schemas['ApiErrorResponse']
export type PriorityResponse = Schemas['PriorityResponse']

export const CATEGORIES = [
  'pothole',
  'blocked_drain',
  'flooding',
  'rubbish',
  'street_light',
  'other',
] as const
export type Category = (typeof CATEGORIES)[number]

export const CLUSTERING_STATUSES = ['confirmed', 'isolated', 'conflict'] as const
export type ClusteringStatus = (typeof CLUSTERING_STATUSES)[number]

export const PRIORITY_LEVELS = [
  'critical',
  'high',
  'medium',
  'low',
  'review_required',
] as const
export type PriorityLevel = (typeof PRIORITY_LEVELS)[number]

export interface IncidentListParams {
  status?: ClusteringStatus
  priority?: PriorityLevel
  category?: Category
  limit?: number
  offset?: number
}

export interface ReviewListParams {
  status?: 'pending' | 'approved' | 'rejected'
  limit?: number
  offset?: number
}
```

- [ ] **Step 3: Write the failing client test `src/api/client.test.ts`**

```ts
import { describe, expect, it, vi } from 'vitest'
import { ApiClient } from './client'
import { ApiConnectivityError, ApiRequestError } from './errors'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('ApiClient', () => {
  it('builds incident list URLs with only the provided filters', async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      jsonResponse({ items: [], limit: 50, offset: 0, total: 0 }),
    )
    const client = new ApiClient('/api/v1', fetchFn)
    await client.listIncidents({ status: 'confirmed', limit: 100 })
    expect(fetchFn).toHaveBeenCalledWith(
      '/api/v1/incidents?status=confirmed&limit=100',
      expect.objectContaining({ headers: expect.anything() }),
    )
  })

  it('maps API error bodies to ApiRequestError', async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'incident_not_found',
            message: 'The requested incident snapshot was not found.',
            details: {},
            request_id: 'req-1',
          },
        },
        404,
      ),
    )
    const client = new ApiClient('/api/v1', fetchFn)
    await expect(client.getIncident('abc')).rejects.toMatchObject({
      code: 'incident_not_found',
      status: 404,
      requestId: 'req-1',
    } satisfies Partial<ApiRequestError>)
  })

  it('maps network failures to ApiConnectivityError', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError('fetch failed'))
    const client = new ApiClient('/api/v1', fetchFn)
    await expect(client.healthReady()).rejects.toBeInstanceOf(ApiConnectivityError)
  })

  it('sends the Idempotency-Key header on complaint submission', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({}, 201))
    const client = new ApiClient('/api/v1', fetchFn)
    await client.submitComplaint(
      {
        text: 'Lampu jalan rosak depan blok',
        latitude: 3.094,
        longitude: 101.505,
        reported_at: '2026-07-17T02:00:00+00:00',
        category: null,
        photo_path: null,
      },
      'key-123',
    )
    const [, init] = fetchFn.mock.calls[0]
    expect(init.method).toBe('POST')
    expect(init.headers['Idempotency-Key']).toBe('key-123')
  })
})
```

- [ ] **Step 4: Run to verify failure**

Run: `npm run test -- --run src/api/client.test.ts`
Expected: FAIL, cannot resolve `./client` / `./errors`.

- [ ] **Step 5: Write `src/api/errors.ts`**

```ts
export class ApiRequestError extends Error {
  constructor(
    readonly code: string,
    readonly userMessage: string,
    readonly requestId: string | null,
    readonly status: number,
  ) {
    super(userMessage)
    this.name = 'ApiRequestError'
  }
}

export class ApiConnectivityError extends Error {
  constructor() {
    super(
      'Cannot reach the CivicPulse API. Start it with: uv run --offline uvicorn civicpulse.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8000',
    )
    this.name = 'ApiConnectivityError'
  }
}

export function toUserMessage(error: unknown): string {
  if (error instanceof ApiRequestError || error instanceof ApiConnectivityError) {
    return error.message
  }
  return 'Something went wrong while talking to the CivicPulse API.'
}
```

- [ ] **Step 6: Write `src/api/client.ts`**

```ts
import type {
  ApiErrorResponse,
  ComplaintCreateRequest,
  ComplaintSubmissionResponse,
  HealthResponse,
  IncidentDetail,
  IncidentListParams,
  IncidentListResponse,
  ReviewDetail,
  ReviewListParams,
  ReviewListResponse,
  ReviewMutationResponse,
  ReviewResolutionRequest,
} from './types'
import { ApiConnectivityError, ApiRequestError } from './errors'

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

export class ApiClient {
  constructor(
    private readonly baseUrl: string = '/api/v1',
    private readonly fetchFn: FetchLike = (input, init) => globalThis.fetch(input, init),
  ) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response
    try {
      response = await this.fetchFn(`${this.baseUrl}${path}`, {
        ...init,
        headers: { Accept: 'application/json', ...(init?.headers ?? {}) },
      })
    } catch {
      throw new ApiConnectivityError()
    }
    if (!response.ok) {
      let code = 'unknown_error'
      let message = `The API request failed with status ${response.status}.`
      let requestId: string | null = null
      try {
        const body = (await response.json()) as ApiErrorResponse
        code = body.error.code
        message = body.error.message
        requestId = body.error.request_id
      } catch {
        // Non-JSON error body; keep the status-based message.
      }
      throw new ApiRequestError(code, message, requestId, response.status)
    }
    return (await response.json()) as T
  }

  healthReady(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health/ready')
  }

  listIncidents(params: IncidentListParams = {}): Promise<IncidentListResponse> {
    return this.request<IncidentListResponse>(`/incidents${toQuery({ ...params })}`)
  }

  getIncident(incidentId: string): Promise<IncidentDetail> {
    return this.request<IncidentDetail>(`/incidents/${incidentId}`)
  }

  listReviews(params: ReviewListParams = {}): Promise<ReviewListResponse> {
    return this.request<ReviewListResponse>(`/reviews${toQuery({ ...params })}`)
  }

  getReview(reviewId: string): Promise<ReviewDetail> {
    return this.request<ReviewDetail>(`/reviews/${reviewId}`)
  }

  approveReview(
    reviewId: string,
    body: ReviewResolutionRequest,
  ): Promise<ReviewMutationResponse> {
    return this.request<ReviewMutationResponse>(`/reviews/${reviewId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  rejectReview(
    reviewId: string,
    body: ReviewResolutionRequest,
  ): Promise<ReviewMutationResponse> {
    return this.request<ReviewMutationResponse>(`/reviews/${reviewId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  submitComplaint(
    body: ComplaintCreateRequest,
    idempotencyKey: string,
  ): Promise<ComplaintSubmissionResponse> {
    return this.request<ComplaintSubmissionResponse>('/complaints', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(body),
    })
  }
}
```

And `src/api/index.ts`:

```ts
import { ApiClient } from './client'

export const api = new ApiClient()
```

- [ ] **Step 7: Run to verify pass**

Run: `npm run test -- --run src/api/client.test.ts`
Expected: 4 passed.
Run: `npm run typecheck`
Expected: 0 errors. If schema aliases mismatch generated names, fix `types.ts` aliases now.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/api frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): typed API client generated from frozen OpenAPI v1 snapshot"
```

---

### Task 3: Presentation domain (category colors, priority labels, formatting)

**Files:**
- Create: `frontend/src/domain/categories.ts`
- Create: `frontend/src/domain/priority.ts`
- Create: `frontend/src/domain/format.ts`
- Test: `frontend/src/domain/format.test.ts`

**Interfaces:**
- Consumes: `Category`, `PriorityLevel`, `ClusteringStatus` from `src/api/types`
- Produces: `CATEGORY_META: Record<Category, { label: string; color: string; heatLow: string }>`, `primaryCategory(summary: Category[]): Category`, `PRIORITY_META`, `STATUS_META`, `formatDateTime(iso: string): string`, `formatCoords(lat: number, lng: number): string`, `formatMetres(m: number): string`, `formatPercent(x: number): string`, `formatDuration(seconds: number): string`.

- [ ] **Step 1: Write the failing test `src/domain/format.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import {
  formatCoords,
  formatDuration,
  formatMetres,
  formatPercent,
} from './format'
import { CATEGORY_META, primaryCategory } from './categories'

describe('formatting', () => {
  it('formats coordinates to five decimals', () => {
    expect(formatCoords(3.0940123, 101.5050987)).toBe('3.09401, 101.50510')
  })

  it('formats metres with one decimal', () => {
    expect(formatMetres(123.456)).toBe('123.5 m')
  })

  it('formats ratios as percentages', () => {
    expect(formatPercent(0.8734)).toBe('87.3%')
  })

  it('humanizes durations', () => {
    expect(formatDuration(90)).toBe('2 min')
    expect(formatDuration(7200)).toBe('2 h')
    expect(formatDuration(180000)).toBe('2 days')
  })
})

describe('categories', () => {
  it('covers every category with a label and color', () => {
    expect(Object.keys(CATEGORY_META)).toHaveLength(6)
    for (const meta of Object.values(CATEGORY_META)) {
      expect(meta.label.length).toBeGreaterThan(0)
      expect(meta.color).toMatch(/^#[0-9a-f]{6}$/)
    }
  })

  it('falls back to other for empty category summaries', () => {
    expect(primaryCategory([])).toBe('other')
    expect(primaryCategory(['flooding', 'pothole'])).toBe('flooding')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/domain/format.test.ts`
Expected: FAIL, modules not found.

- [ ] **Step 3: Write `src/domain/categories.ts`**

```ts
import type { Category } from '../api/types'

export interface CategoryMeta {
  label: string
  color: string
  /** Same hue at 25% alpha, used as the low end of the map heat ramp. */
  heatLow: string
}

export const CATEGORY_META: Record<Category, CategoryMeta> = {
  pothole: { label: 'Pothole', color: '#d55e00', heatLow: 'rgba(213, 94, 0, 0.25)' },
  blocked_drain: {
    label: 'Blocked drain',
    color: '#56b4e9',
    heatLow: 'rgba(86, 180, 233, 0.25)',
  },
  flooding: { label: 'Flooding', color: '#0072b2', heatLow: 'rgba(0, 114, 178, 0.25)' },
  rubbish: { label: 'Rubbish', color: '#009e73', heatLow: 'rgba(0, 158, 115, 0.25)' },
  street_light: {
    label: 'Street light',
    color: '#e69f00',
    heatLow: 'rgba(230, 159, 0, 0.25)',
  },
  other: { label: 'Other', color: '#6e7781', heatLow: 'rgba(110, 119, 129, 0.25)' },
}

export function primaryCategory(summary: readonly Category[]): Category {
  return summary[0] ?? 'other'
}
```

- [ ] **Step 4: Write `src/domain/priority.ts`**

```ts
import type { ClusteringStatus, PriorityLevel } from '../api/types'

export interface BadgeMeta {
  label: string
  bgVar: string
  textVar: string
}

export const PRIORITY_META: Record<PriorityLevel, BadgeMeta> = {
  critical: { label: 'Critical', bgVar: '--prio-critical-bg', textVar: '--prio-critical-text' },
  high: { label: 'High', bgVar: '--prio-high-bg', textVar: '--prio-high-text' },
  medium: { label: 'Medium', bgVar: '--prio-medium-bg', textVar: '--prio-medium-text' },
  low: { label: 'Low', bgVar: '--prio-low-bg', textVar: '--prio-low-text' },
  review_required: {
    label: 'Review required',
    bgVar: '--prio-none-bg',
    textVar: '--prio-none-text',
  },
}

/** Conflict incidents intentionally have no priority; this is a safety outcome. */
export const PRIORITY_UNAVAILABLE: BadgeMeta = {
  label: 'No operational priority',
  bgVar: '--prio-none-bg',
  textVar: '--prio-none-text',
}

export const STATUS_META: Record<ClusteringStatus, BadgeMeta> = {
  confirmed: { label: 'Confirmed', bgVar: '--status-confirmed-bg', textVar: '--status-confirmed-text' },
  isolated: { label: 'Isolated', bgVar: '--status-isolated-bg', textVar: '--status-isolated-text' },
  conflict: { label: 'Conflict', bgVar: '--status-conflict-bg', textVar: '--status-conflict-text' },
}
```

- [ ] **Step 5: Write `src/domain/format.ts`**

```ts
const dateTimeFormat = new Intl.DateTimeFormat('en-MY', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso))
}

export function formatCoords(latitude: number, longitude: number): string {
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`
}

export function formatMetres(metres: number): string {
  return `${metres.toFixed(1)} m`
}

export function formatPercent(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`
}

export function formatDuration(seconds: number): string {
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h`
  return `${Math.round(seconds / 86400)} days`
}
```

- [ ] **Step 6: Run to verify pass**

Run: `npm run test -- --run src/domain/format.test.ts`
Expected: 6 passed.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/domain
git commit -m "feat(frontend): category, priority, and formatting presentation domain"
```

---

### Task 4: App shell, router, and readiness gate

**Files:**
- Create: `frontend/src/stores/health.ts`
- Modify: `frontend/src/router.ts` (replace placeholder)
- Modify: `frontend/src/App.vue` (replace placeholder)
- Create: `frontend/src/views/QueueView.vue`, `frontend/src/views/MapView.vue`, `frontend/src/views/SubmitView.vue`, `frontend/src/views/ReviewsView.vue` (placeholder bodies, filled by Tasks 6 to 10)
- Test: `frontend/src/stores/health.test.ts`

**Interfaces:**
- Consumes: `api.healthReady()`, `toUserMessage`
- Produces: `useHealthStore()` with `state: 'loading' | 'ready' | 'not_ready' | 'unreachable'`, `message: string | null`, `refresh(): Promise<void>`; routes `/` (queue), `/map`, `/submit`, `/reviews`.

- [ ] **Step 1: Write the failing store test `src/stores/health.test.ts`**

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const healthReady = vi.fn()
vi.mock('../api', () => ({ api: { healthReady: (...a: unknown[]) => healthReady(...a) } }))

import { useHealthStore } from './health'
import { ApiConnectivityError } from '../api/errors'

describe('health store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    healthReady.mockReset()
  })

  it('is ready when core_ready is true', async () => {
    healthReady.mockResolvedValue({ status: 'healthy', core_ready: true })
    const store = useHealthStore()
    await store.refresh()
    expect(store.state).toBe('ready')
  })

  it('is not_ready when core_ready is false', async () => {
    healthReady.mockResolvedValue({ status: 'degraded', core_ready: false })
    const store = useHealthStore()
    await store.refresh()
    expect(store.state).toBe('not_ready')
  })

  it('is unreachable on connectivity failure', async () => {
    healthReady.mockRejectedValue(new ApiConnectivityError())
    const store = useHealthStore()
    await store.refresh()
    expect(store.state).toBe('unreachable')
    expect(store.message).toContain('Cannot reach')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/stores/health.test.ts`
Expected: FAIL, `./health` not found.

- [ ] **Step 3: Write `src/stores/health.ts`**

```ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api'
import { toUserMessage } from '../api/errors'

export type HealthState = 'loading' | 'ready' | 'not_ready' | 'unreachable'

export const useHealthStore = defineStore('health', () => {
  const state = ref<HealthState>('loading')
  const message = ref<string | null>(null)

  async function refresh(): Promise<void> {
    state.value = 'loading'
    message.value = null
    try {
      const readiness = await api.healthReady()
      state.value = readiness.core_ready ? 'ready' : 'not_ready'
      if (!readiness.core_ready) {
        message.value =
          'Core service is not ready. Incident data is unavailable until readiness checks pass.'
      }
    } catch (error) {
      state.value = 'unreachable'
      message.value = toUserMessage(error)
    }
  }

  return { state, message, refresh }
})
```

- [ ] **Step 4: Run to verify pass**

Run: `npm run test -- --run src/stores/health.test.ts`
Expected: 3 passed.

- [ ] **Step 5: Write the router and placeholder views**

`src/router.ts`:

```ts
import { createRouter, createWebHistory } from 'vue-router'
import QueueView from './views/QueueView.vue'
import MapView from './views/MapView.vue'
import SubmitView from './views/SubmitView.vue'
import ReviewsView from './views/ReviewsView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'queue', component: QueueView },
    { path: '/map', name: 'map', component: MapView },
    { path: '/submit', name: 'submit', component: SubmitView },
    { path: '/reviews', name: 'reviews', component: ReviewsView },
  ],
})
```

Each placeholder view (example `src/views/QueueView.vue`; same shape for MapView, SubmitView, ReviewsView with their own headings "Incident map", "Submit report", "Review queue"):

```vue
<template>
  <section>
    <h2>Operational queue</h2>
  </section>
</template>
```

- [ ] **Step 6: Write the real `src/App.vue`**

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useHealthStore } from './stores/health'

const health = useHealthStore()
onMounted(() => health.refresh())
</script>

<template>
  <div class="shell">
    <header class="shell-header">
      <h1 class="shell-brand">CivicPulse operations</h1>
      <nav class="shell-nav" aria-label="Primary">
        <router-link to="/">Incidents</router-link>
        <router-link to="/map">Map</router-link>
        <router-link to="/submit">Submit report</router-link>
        <router-link to="/reviews">Reviews</router-link>
      </nav>
    </header>

    <main class="shell-main">
      <div v-if="health.state === 'loading'" class="shell-gate" role="status">
        Checking API readiness...
      </div>
      <div v-else-if="health.state !== 'ready'" class="panel-error shell-gate">
        <p>{{ health.message }}</p>
        <button type="button" class="button-secondary" @click="health.refresh()">
          Retry readiness check
        </button>
      </div>
      <router-view v-else />
    </main>

    <footer class="shell-footer">
      <p>
        Demo dataset. All complaints, coordinates, and outcomes are synthetic and modelled
        on a Shah Alam-inspired municipal district. Not live municipal data.
      </p>
    </footer>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}

.shell-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 24px;
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
}

.shell-brand {
  font-size: 18px;
  font-weight: 700;
}

.shell-nav {
  display: flex;
  gap: 4px;
}

.shell-nav a {
  padding: 8px 14px;
  border-radius: var(--radius-control);
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 600;
}

.shell-nav a:hover {
  background: var(--surface-sunken);
}

.shell-nav a.router-link-active {
  color: var(--accent);
  background: var(--accent-tint);
}

.shell-main {
  flex: 1;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.shell-gate {
  max-width: 560px;
  margin: 48px auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.shell-footer {
  padding: 12px 24px;
  border-top: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 12px;
}
</style>
```

- [ ] **Step 7: Verify**

Run: `npm run test -- --run` → all suites pass (App smoke test still passes; if it now needs the health store, the pinia plugin in the test already covers it, but mock `api.healthReady` in `App.test.ts` the same way as the store test if jsdom logs unhandled fetch rejections).
Run: `npm run typecheck` → 0 errors.
Run: `npm run dev` with the API running → tabs render, gate passes; with the API stopped → connectivity panel with retry renders.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src
git commit -m "feat(frontend): app shell, routing, and API readiness gate"
```

---

### Task 5: AccordionCard base component

**Files:**
- Create: `frontend/src/components/AccordionCard.vue`
- Test: `frontend/src/components/AccordionCard.test.ts`

**Interfaces:**
- Consumes: nothing app-specific
- Produces: `<AccordionCard :expanded="bool" :edge-color="'#0072b2'" @toggle>` with slots `summary` (always visible, inside the trigger button) and default (expandable body). Fully keyboard accessible: trigger is a `<button>` with `aria-expanded` and `aria-controls`; body is a labelled region.

- [ ] **Step 1: Write the failing test `src/components/AccordionCard.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AccordionCard from './AccordionCard.vue'

describe('AccordionCard', () => {
  function build(expanded: boolean) {
    return mount(AccordionCard, {
      props: { expanded, edgeColor: '#0072b2' },
      slots: { summary: '<span>Flooding at Kampung Sungai Damai</span>', default: '<p>Body</p>' },
    })
  }

  it('wires aria-expanded and aria-controls to the region id', () => {
    const wrapper = build(false)
    const button = wrapper.get('button')
    expect(button.attributes('aria-expanded')).toBe('false')
    const region = wrapper.get('[role="region"]')
    expect(button.attributes('aria-controls')).toBe(region.attributes('id'))
  })

  it('emits toggle on click', async () => {
    const wrapper = build(false)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('marks the body expanded when open', () => {
    const wrapper = build(true)
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.accordion-body').attributes('data-expanded')).toBe('true')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/components/AccordionCard.test.ts`
Expected: FAIL, component not found.

- [ ] **Step 3: Write `src/components/AccordionCard.vue`**

```vue
<script setup lang="ts">
import { useId } from 'vue'

defineProps<{
  expanded: boolean
  edgeColor?: string
}>()

const emit = defineEmits<{ toggle: [] }>()

const regionId = useId()
const buttonId = useId()
</script>

<template>
  <section class="accordion-card" :style="{ borderLeftColor: edgeColor ?? 'var(--border)' }">
    <h3 class="accordion-heading">
      <button
        :id="buttonId"
        type="button"
        class="accordion-trigger"
        :aria-expanded="expanded"
        :aria-controls="regionId"
        @click="emit('toggle')"
      >
        <span class="accordion-summary"><slot name="summary" /></span>
        <span class="accordion-chevron" :class="{ open: expanded }" aria-hidden="true" />
      </button>
    </h3>
    <div
      :id="regionId"
      role="region"
      :aria-labelledby="buttonId"
      class="accordion-body"
      :data-expanded="expanded"
    >
      <div class="accordion-body-inner">
        <div class="accordion-content">
          <slot />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.accordion-card {
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-left-width: 3px;
  border-radius: var(--radius-card);
}

.accordion-heading {
  margin: 0;
}

.accordion-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  background: none;
  border: none;
  border-radius: var(--radius-card);
  text-align: left;
  color: inherit;
}

.accordion-trigger:hover {
  background: var(--surface-sunken);
}

.accordion-summary {
  flex: 1;
  min-width: 0;
}

/* CSS-drawn chevron; no icon library needed. */
.accordion-chevron {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--text-muted);
  border-bottom: 2px solid var(--text-muted);
  transform: rotate(45deg);
  transition: transform 200ms ease;
}

.accordion-chevron.open {
  transform: rotate(225deg);
}

.accordion-body {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 200ms ease;
}

.accordion-body[data-expanded='true'] {
  grid-template-rows: 1fr;
}

.accordion-body-inner {
  overflow: hidden;
}

.accordion-content {
  padding: 0 16px 16px;
  border-top: 1px solid var(--border);
  padding-top: 12px;
  margin: 0 0;
}

@media (prefers-reduced-motion: reduce) {
  .accordion-body,
  .accordion-chevron {
    transition: none;
  }
}
</style>
```

- [ ] **Step 4: Run to verify pass**

Run: `npm run test -- --run src/components/AccordionCard.test.ts`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/AccordionCard.vue frontend/src/components/AccordionCard.test.ts
git commit -m "feat(frontend): accessible animated accordion card component"
```

---

### Task 6: Badges, chips, incidents store, and the operational queue view

**Files:**
- Create: `frontend/src/components/CategoryChip.vue`
- Create: `frontend/src/components/PriorityBadge.vue`
- Create: `frontend/src/components/StatusBadge.vue`
- Create: `frontend/src/stores/incidents.ts`
- Create: `frontend/src/components/incidents/IncidentSummaryRow.vue`
- Modify: `frontend/src/views/QueueView.vue` (replace placeholder)
- Test: `frontend/src/stores/incidents.test.ts`

**Interfaces:**
- Consumes: `api.listIncidents`, `api.getIncident`, `AccordionCard`, `CATEGORY_META`, `PRIORITY_META`, `STATUS_META`, formatters
- Produces: `useIncidentsStore()` with `items: IncidentSummary[]`, `total`, `loading`, `error`, `filters: { status?, priority?, category? }`, `load(): Promise<void>`, `detailFor(id): IncidentDetail | undefined`, `detailError(id): string | undefined`, `loadDetail(id): Promise<void>`; `IncidentSummaryRow` (props `incident: IncidentSummary`) used by both queue and map popup follow-ups; Task 7 fills the expanded panel.

- [ ] **Step 1: Write the failing store test `src/stores/incidents.test.ts`**

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const listIncidents = vi.fn()
const getIncident = vi.fn()
vi.mock('../api', () => ({
  api: {
    listIncidents: (...a: unknown[]) => listIncidents(...a),
    getIncident: (...a: unknown[]) => getIncident(...a),
  },
}))

import { useIncidentsStore } from './incidents'

const summary = {
  incident_id: 'a1',
  status: 'confirmed',
  category_summary: ['flooding'],
  priority: { level: 'high', reasons: ['confirmed flooding'], policy_version: 'priority-v1' },
  confirmed_report_count: 4,
  pending_candidate_count: 1,
  centroid: { latitude: 3.046, longitude: 101.519 },
  radius_metres: 120.5,
  earliest_reported_at: '2026-07-10T01:00:00Z',
  latest_reported_at: '2026-07-15T09:30:00Z',
  conflict_reasons: [],
}

describe('incidents store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listIncidents.mockReset()
    getIncident.mockReset()
  })

  it('loads a page and applies filters', async () => {
    listIncidents.mockResolvedValue({ items: [summary], limit: 50, offset: 0, total: 1 })
    const store = useIncidentsStore()
    store.filters.status = 'confirmed'
    await store.load()
    expect(listIncidents).toHaveBeenCalledWith({ status: 'confirmed', limit: 50, offset: 0 })
    expect(store.items).toHaveLength(1)
    expect(store.error).toBeNull()
  })

  it('caches detail per incident id', async () => {
    getIncident.mockResolvedValue({ ...summary, complaint_ids: [], review_candidate_ids: [], confirmed_edges: [], review_candidates: [] })
    const store = useIncidentsStore()
    await store.loadDetail('a1')
    await store.loadDetail('a1')
    expect(getIncident).toHaveBeenCalledTimes(1)
    expect(store.detailFor('a1')?.incident_id).toBe('a1')
  })

  it('captures list errors as user messages', async () => {
    listIncidents.mockRejectedValue(new Error('boom'))
    const store = useIncidentsStore()
    await store.load()
    expect(store.error).not.toBeNull()
    expect(store.items).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/stores/incidents.test.ts`
Expected: FAIL, `./incidents` not found.

- [ ] **Step 3: Write `src/stores/incidents.ts`**

```ts
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { api } from '../api'
import { toUserMessage } from '../api/errors'
import type {
  Category,
  ClusteringStatus,
  IncidentDetail,
  IncidentSummary,
  PriorityLevel,
} from '../api/types'

interface IncidentFilters {
  status?: ClusteringStatus
  priority?: PriorityLevel
  category?: Category
}

export const useIncidentsStore = defineStore('incidents', () => {
  const items = ref<IncidentSummary[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const filters = reactive<IncidentFilters>({})

  const details = reactive(new Map<string, IncidentDetail>())
  const detailErrors = reactive(new Map<string, string>())
  const detailLoading = reactive(new Set<string>())

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const page = await api.listIncidents({ ...filters, limit: 50, offset: 0 })
      items.value = page.items
      total.value = page.total
    } catch (err) {
      error.value = toUserMessage(err)
      items.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  async function loadDetail(incidentId: string): Promise<void> {
    if (details.has(incidentId) || detailLoading.has(incidentId)) return
    detailLoading.add(incidentId)
    detailErrors.delete(incidentId)
    try {
      details.set(incidentId, await api.getIncident(incidentId))
    } catch (err) {
      detailErrors.set(incidentId, toUserMessage(err))
    } finally {
      detailLoading.delete(incidentId)
    }
  }

  const detailFor = (id: string): IncidentDetail | undefined => details.get(id)
  const detailError = (id: string): string | undefined => detailErrors.get(id)
  const isDetailLoading = (id: string): boolean => detailLoading.has(id)

  return {
    items,
    total,
    loading,
    error,
    filters,
    load,
    loadDetail,
    detailFor,
    detailError,
    isDetailLoading,
  }
})
```

- [ ] **Step 4: Run to verify pass**

Run: `npm run test -- --run src/stores/incidents.test.ts`
Expected: 3 passed.

- [ ] **Step 5: Write the badge and chip components**

`src/components/CategoryChip.vue`:

```vue
<script setup lang="ts">
import type { Category } from '../api/types'
import { CATEGORY_META } from '../domain/categories'

const props = defineProps<{ category: Category }>()
const meta = CATEGORY_META[props.category]
</script>

<template>
  <span class="chip">
    <span class="chip-dot" :style="{ background: meta.color }" aria-hidden="true" />
    {{ meta.label }}
  </span>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--surface-raised);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>
```

`src/components/PriorityBadge.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { PriorityResponse } from '../api/types'
import { PRIORITY_META, PRIORITY_UNAVAILABLE } from '../domain/priority'

const props = defineProps<{ priority: PriorityResponse | null | undefined }>()

const meta = computed(() =>
  props.priority ? PRIORITY_META[props.priority.level] : PRIORITY_UNAVAILABLE,
)
</script>

<template>
  <span
    class="badge"
    :style="{ background: `var(${meta.bgVar})`, color: `var(${meta.textVar})` }"
  >
    {{ meta.label }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
</style>
```

`src/components/StatusBadge.vue`:

```vue
<script setup lang="ts">
import type { ClusteringStatus } from '../api/types'
import { STATUS_META } from '../domain/priority'

const props = defineProps<{ status: ClusteringStatus }>()
const meta = STATUS_META[props.status]
</script>

<template>
  <span
    class="badge"
    :style="{ background: `var(${meta.bgVar})`, color: `var(${meta.textVar})` }"
  >
    {{ meta.label }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
</style>
```

- [ ] **Step 6: Write `src/components/incidents/IncidentSummaryRow.vue`**

```vue
<script setup lang="ts">
import type { IncidentSummary } from '../../api/types'
import { formatDateTime } from '../../domain/format'
import CategoryChip from '../CategoryChip.vue'
import PriorityBadge from '../PriorityBadge.vue'
import StatusBadge from '../StatusBadge.vue'

defineProps<{ incident: IncidentSummary }>()
</script>

<template>
  <div class="row">
    <div class="row-chips">
      <CategoryChip
        v-for="category in incident.category_summary"
        :key="category"
        :category="category"
      />
      <StatusBadge :status="incident.status" />
      <PriorityBadge :priority="incident.priority" />
    </div>
    <div class="row-counts">
      <span class="mono">{{ incident.confirmed_report_count }} confirmed</span>
      <span v-if="incident.pending_candidate_count > 0" class="mono pending">
        {{ incident.pending_candidate_count }} pending review
      </span>
      <span class="row-time">Latest {{ formatDateTime(incident.latest_reported_at) }}</span>
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
}

.row-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.row-counts {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.pending {
  color: var(--prio-high-text);
}

.row-time {
  color: var(--text-muted);
}
</style>
```

- [ ] **Step 7: Write the real `src/views/QueueView.vue`**

Uses a placeholder detail body ("Loading incident detail...") that Task 7 replaces with `IncidentDetailPanel`.

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useIncidentsStore } from '../stores/incidents'
import { CATEGORIES, CLUSTERING_STATUSES, PRIORITY_LEVELS } from '../api/types'
import { CATEGORY_META, primaryCategory } from '../domain/categories'
import AccordionCard from '../components/AccordionCard.vue'
import IncidentSummaryRow from '../components/incidents/IncidentSummaryRow.vue'

const store = useIncidentsStore()
const expandedId = ref<string | null>(null)

onMounted(() => store.load())

function toggle(incidentId: string): void {
  if (expandedId.value === incidentId) {
    expandedId.value = null
    return
  }
  expandedId.value = incidentId
  void store.loadDetail(incidentId)
}
</script>

<template>
  <section>
    <header class="queue-header">
      <h2>Operational queue</h2>
      <p class="queue-caption">
        Incidents ranked by the API. Confirmed and pending counts are kept separate.
      </p>
    </header>

    <form class="filters" @submit.prevent="store.load()">
      <label class="field">
        <span class="field-label">Status</span>
        <select v-model="store.filters.status" class="control" @change="store.load()">
          <option :value="undefined">All statuses</option>
          <option v-for="status in CLUSTERING_STATUSES" :key="status" :value="status">
            {{ status }}
          </option>
        </select>
      </label>
      <label class="field">
        <span class="field-label">Priority</span>
        <select v-model="store.filters.priority" class="control" @change="store.load()">
          <option :value="undefined">All priorities</option>
          <option v-for="level in PRIORITY_LEVELS" :key="level" :value="level">
            {{ level }}
          </option>
        </select>
      </label>
      <label class="field">
        <span class="field-label">Category</span>
        <select v-model="store.filters.category" class="control" @change="store.load()">
          <option :value="undefined">All categories</option>
          <option v-for="category in CATEGORIES" :key="category" :value="category">
            {{ CATEGORY_META[category].label }}
          </option>
        </select>
      </label>
      <p class="filters-total mono" aria-live="polite">{{ store.total }} incidents</p>
    </form>

    <div v-if="store.error" class="panel-error">
      <p>{{ store.error }}</p>
      <button type="button" class="button-secondary" @click="store.load()">Retry</button>
    </div>

    <p v-else-if="store.loading" role="status">Loading incidents...</p>

    <p v-else-if="store.items.length === 0" class="empty">
      No incidents match these filters. Clear a filter or submit a report to see new incidents.
    </p>

    <ul v-else class="queue-list">
      <li v-for="incident in store.items" :key="incident.incident_id">
        <AccordionCard
          :expanded="expandedId === incident.incident_id"
          :edge-color="CATEGORY_META[primaryCategory(incident.category_summary)].color"
          @toggle="toggle(incident.incident_id)"
        >
          <template #summary>
            <IncidentSummaryRow :incident="incident" />
          </template>
          <p v-if="store.isDetailLoading(incident.incident_id)" role="status">
            Loading incident detail...
          </p>
          <p v-else-if="store.detailError(incident.incident_id)" class="field-error">
            {{ store.detailError(incident.incident_id) }}
          </p>
          <p v-else-if="store.detailFor(incident.incident_id)">
            Detail panel arrives in Task 7.
          </p>
        </AccordionCard>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.queue-header {
  margin-bottom: 16px;
}

.queue-header h2 {
  font-size: 22px;
}

.queue-caption {
  color: var(--text-secondary);
  font-size: 13px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
  padding: 12px;
  margin-bottom: 16px;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
}

.filters-total {
  margin-left: auto;
  color: var(--text-secondary);
}

.queue-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.empty {
  color: var(--text-secondary);
  padding: 32px 0;
  text-align: center;
}
</style>
```

- [ ] **Step 8: Verify**

Run: `npm run test -- --run` → all pass.
Run: `npm run typecheck` → 0 errors.
Run: `npm run dev` with the API running → queue renders seeded incidents, filters work, cards expand with the temporary detail message.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src
git commit -m "feat(frontend): operational queue with accordion incident cards and filters"
```

---

### Task 7: Incident detail panel

**Files:**
- Create: `frontend/src/components/incidents/IncidentDetailPanel.vue`
- Modify: `frontend/src/views/QueueView.vue` (swap the Task 6 placeholder for the panel)

**Interfaces:**
- Consumes: `IncidentDetail` from `src/api/types`, formatters, badges
- Produces: `<IncidentDetailPanel :detail="IncidentDetail" />` rendering overview facts, priority reasons, conflict reasons, confirmed relationships, and pending review candidates (with a link to the Reviews view).

- [ ] **Step 1: Write `src/components/incidents/IncidentDetailPanel.vue`**

```vue
<script setup lang="ts">
import type { IncidentDetail } from '../../api/types'
import { formatCoords, formatDateTime, formatMetres } from '../../domain/format'

defineProps<{ detail: IncidentDetail }>()

function shortId(id: string): string {
  return id.slice(0, 8)
}
</script>

<template>
  <div class="detail">
    <dl class="facts">
      <div class="fact">
        <dt>Centroid</dt>
        <dd class="mono">{{ formatCoords(detail.centroid.latitude, detail.centroid.longitude) }}</dd>
      </div>
      <div class="fact">
        <dt>Radius</dt>
        <dd class="mono">{{ formatMetres(detail.radius_metres) }}</dd>
      </div>
      <div class="fact">
        <dt>First report</dt>
        <dd>{{ formatDateTime(detail.earliest_reported_at) }}</dd>
      </div>
      <div class="fact">
        <dt>Latest report</dt>
        <dd>{{ formatDateTime(detail.latest_reported_at) }}</dd>
      </div>
      <div class="fact">
        <dt>Complaints</dt>
        <dd class="mono">{{ detail.complaint_ids.length }}</dd>
      </div>
      <div class="fact">
        <dt>Snapshot ID</dt>
        <dd class="mono">{{ shortId(detail.incident_id) }}</dd>
      </div>
    </dl>

    <section v-if="detail.priority" class="block">
      <h4>Why this priority</h4>
      <ul class="reason-list">
        <li v-for="reason in detail.priority.reasons" :key="reason">{{ reason }}</li>
      </ul>
      <p class="policy mono">Policy {{ detail.priority.policy_version }}</p>
    </section>

    <section v-else class="block">
      <h4>No operational priority</h4>
      <p class="muted">
        Priority is intentionally withheld until conflicting evidence is resolved. This is a
        safety outcome, not missing data.
      </p>
    </section>

    <section v-if="detail.conflict_reasons.length > 0" class="block conflict">
      <h4>Conflict reasons</h4>
      <ul class="reason-list">
        <li v-for="reason in detail.conflict_reasons" :key="reason">{{ reason }}</li>
      </ul>
    </section>

    <section v-if="detail.confirmed_edges.length > 0" class="block">
      <h4>Confirmed relationships</h4>
      <ul class="edge-list">
        <li v-for="edge in detail.confirmed_edges" :key="`${edge.left_id}-${edge.right_id}`">
          <span class="mono">{{ shortId(edge.left_id) }} and {{ shortId(edge.right_id) }}</span>
          <span class="edge-source">
            {{ edge.decision_source === 'officer_review' ? 'Officer decision' : 'Automatic match' }}
          </span>
          <ul class="reason-list">
            <li v-for="reason in edge.reasons" :key="reason">{{ reason }}</li>
          </ul>
        </li>
      </ul>
    </section>

    <section v-if="detail.review_candidates.length > 0" class="block">
      <h4>Pending review candidates</h4>
      <ul class="edge-list">
        <li v-for="edge in detail.review_candidates" :key="`${edge.left_id}-${edge.right_id}`">
          <span class="mono">{{ shortId(edge.left_id) }} and {{ shortId(edge.right_id) }}</span>
          <ul class="reason-list">
            <li v-for="reason in edge.reasons" :key="reason">{{ reason }}</li>
          </ul>
        </li>
      </ul>
      <router-link to="/reviews">Open the review queue</router-link>
    </section>
  </div>
</template>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px 16px;
  margin: 0;
  padding: 12px;
  background: var(--surface-sunken);
  border-radius: var(--radius-control);
}

.fact dt {
  font-size: 12px;
  color: var(--text-muted);
}

.fact dd {
  margin: 0;
  font-size: 13px;
}

.block h4 {
  font-size: 14px;
  margin-bottom: 6px;
}

.reason-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 13px;
}

.policy {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 4px;
}

.muted {
  color: var(--text-secondary);
  font-size: 13px;
}

.conflict h4 {
  color: var(--status-conflict-text);
}

.edge-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.edge-source {
  margin-left: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

a {
  color: var(--accent);
  font-weight: 600;
}
</style>
```

- [ ] **Step 2: Wire it into `QueueView.vue`**

Replace the Task 6 placeholder line inside the AccordionCard default slot:

```vue
<IncidentDetailPanel
  v-else-if="store.detailFor(incident.incident_id)"
  :detail="store.detailFor(incident.incident_id)!"
/>
```

and add the import:

```ts
import IncidentDetailPanel from '../components/incidents/IncidentDetailPanel.vue'
```

- [ ] **Step 3: Verify**

Run: `npm run test -- --run` and `npm run typecheck` → all green.
Run: `npm run dev` with the API running → expanding a card shows facts, priority reasons, and for a conflict incident the "No operational priority" explanation plus conflict reasons.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src
git commit -m "feat(frontend): incident detail panel with priority and conflict explanations"
```

---

### Task 8: Map view with per-category heatmap (MapLibre GL)

**Files:**
- Create: `frontend/src/components/map/geojson.ts`
- Create: `frontend/src/components/map/MapLegend.vue`
- Create: `frontend/src/components/map/IncidentMap.vue`
- Modify: `frontend/src/views/MapView.vue` (replace placeholder)
- Test: `frontend/src/components/map/geojson.test.ts`

**Interfaces:**
- Consumes: `api.listIncidents({ status: 'confirmed', priority?, limit: 100 })`, `CATEGORY_META`, `primaryCategory`, `PRIORITY_LEVELS`
- Produces: `severityRank(level: string | null | undefined): number` (1 to 4, pure, tested); `incidentsToGeoJson(items: IncidentSummary[]): GeoJSON.FeatureCollection` (pure, tested, includes a `severity` property per feature); `<IncidentMap :incidents="IncidentSummary[]" :visible-categories="Set<Category>" />`; `<MapLegend v-model:visible="Set<Category>" />`. Only confirmed incidents are plotted; heat weight comes from `confirmed_report_count` only; heat coverage (radius) scales with `severity` so critical incidents visibly occupy more area. MapView adds a priority filter that re-queries the API.

- [ ] **Step 1: Write the failing projection test `src/components/map/geojson.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { incidentsToGeoJson, severityRank } from './geojson'
import type { IncidentSummary } from '../../api/types'

const base: IncidentSummary = {
  incident_id: 'a1',
  status: 'confirmed',
  category_summary: ['flooding', 'blocked_drain'],
  priority: { level: 'high', reasons: [], policy_version: 'priority-v1' },
  confirmed_report_count: 4,
  pending_candidate_count: 2,
  centroid: { latitude: 3.046, longitude: 101.519 },
  radius_metres: 120.5,
  earliest_reported_at: '2026-07-10T01:00:00Z',
  latest_reported_at: '2026-07-15T09:30:00Z',
  conflict_reasons: [],
}

describe('incidentsToGeoJson', () => {
  it('projects confirmed incidents to point features in lng-lat order', () => {
    const collection = incidentsToGeoJson([base])
    expect(collection.features).toHaveLength(1)
    const feature = collection.features[0]
    expect(feature.geometry).toEqual({ type: 'Point', coordinates: [101.519, 3.046] })
    expect(feature.properties).toMatchObject({
      id: 'a1',
      primaryCategory: 'flooding',
      reports: 4,
      priority: 'high',
      severity: 3,
    })
  })

  it('drops non-confirmed incidents so pending evidence never inflates the map', () => {
    const collection = incidentsToGeoJson([{ ...base, status: 'isolated' }])
    expect(collection.features).toHaveLength(0)
  })

  it('labels missing priority explicitly and gives it the lowest severity', () => {
    const collection = incidentsToGeoJson([{ ...base, priority: null }])
    expect(collection.features[0].properties?.priority).toBe('unavailable')
    expect(collection.features[0].properties?.severity).toBe(1)
  })

  it('ranks severity from priority level for heat coverage', () => {
    expect(severityRank('critical')).toBe(4)
    expect(severityRank('high')).toBe(3)
    expect(severityRank('medium')).toBe(2)
    expect(severityRank('low')).toBe(1)
    expect(severityRank('review_required')).toBe(1)
    expect(severityRank(null)).toBe(1)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/components/map/geojson.test.ts`
Expected: FAIL, module not found.

- [ ] **Step 3: Write `src/components/map/geojson.ts`**

```ts
import type { FeatureCollection, Point } from 'geojson'
import type { IncidentSummary } from '../../api/types'
import { primaryCategory } from '../../domain/categories'

export interface IncidentFeatureProperties {
  id: string
  primaryCategory: string
  reports: number
  pending: number
  priority: string
  /** 1 (low or unavailable) to 4 (critical); drives heat coverage radius. */
  severity: number
  latestReportedAt: string
  [key: string]: unknown
}

export function severityRank(level: string | null | undefined): number {
  switch (level) {
    case 'critical':
      return 4
    case 'high':
      return 3
    case 'medium':
      return 2
    default:
      return 1
  }
}

export function incidentsToGeoJson(
  items: readonly IncidentSummary[],
): FeatureCollection<Point, IncidentFeatureProperties> {
  return {
    type: 'FeatureCollection',
    features: items
      .filter((incident) => incident.status === 'confirmed')
      .map((incident) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'Point' as const,
          coordinates: [incident.centroid.longitude, incident.centroid.latitude],
        },
        properties: {
          id: incident.incident_id,
          primaryCategory: primaryCategory(incident.category_summary),
          reports: incident.confirmed_report_count,
          pending: incident.pending_candidate_count,
          priority: incident.priority?.level ?? 'unavailable',
          severity: severityRank(incident.priority?.level ?? null),
          latestReportedAt: incident.latest_reported_at,
        },
      })),
  }
}
```

Note: `geojson` types ship with `maplibre-gl` via `@types/geojson`; if the import fails, run `npm install -D @types/geojson`.

- [ ] **Step 4: Run to verify pass**

Run: `npm run test -- --run src/components/map/geojson.test.ts`
Expected: 3 passed.

- [ ] **Step 5: Write `src/components/map/MapLegend.vue`**

```vue
<script setup lang="ts">
import type { Category } from '../../api/types'
import { CATEGORIES } from '../../api/types'
import { CATEGORY_META } from '../../domain/categories'

const props = defineProps<{ visible: Set<Category> }>()
const emit = defineEmits<{ 'update:visible': [Set<Category>] }>()

function toggle(category: Category): void {
  const next = new Set(props.visible)
  if (next.has(category)) next.delete(category)
  else next.add(category)
  emit('update:visible', next)
}
</script>

<template>
  <fieldset class="legend">
    <legend>Incident categories</legend>
    <label v-for="category in CATEGORIES" :key="category" class="legend-item">
      <input
        type="checkbox"
        :checked="visible.has(category)"
        @change="toggle(category)"
      />
      <span class="legend-swatch" :style="{ background: CATEGORY_META[category].color }" aria-hidden="true" />
      {{ CATEGORY_META[category].label }}
    </label>
  </fieldset>
</template>

<style scoped>
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--surface-raised);
}

.legend legend {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 0 4px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.legend-swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}
</style>
```

- [ ] **Step 6: Write `src/components/map/IncidentMap.vue`**

All imperative MapLibre code lives here. One heatmap layer plus one circle layer per category, each tinted with that category's color. Heat intensity is weighted by confirmed report count; heat coverage radius scales with the `severity` property (priority level), so more severe incidents claim more area. Legend toggles flip layer visibility.

```vue
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Category, IncidentSummary } from '../../api/types'
import { CATEGORIES } from '../../api/types'
import { CATEGORY_META } from '../../domain/categories'
import { formatDateTime } from '../../domain/format'
import { incidentsToGeoJson } from './geojson'

const props = defineProps<{
  incidents: IncidentSummary[]
  visibleCategories: Set<Category>
}>()

const container = ref<HTMLDivElement | null>(null)
let map: maplibregl.Map | null = null

const DEMO_CENTER: [number, number] = [101.52, 3.07]

const BASE_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    basemap: {
      type: 'raster',
      tiles: ['https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png'],
      tileSize: 256,
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    },
  },
  layers: [
    { id: 'background', type: 'background', paint: { 'background-color': '#eef1f4' } },
    { id: 'basemap', type: 'raster', source: 'basemap' },
  ],
}

function addIncidentLayers(target: maplibregl.Map): void {
  target.addSource('incidents', {
    type: 'geojson',
    data: incidentsToGeoJson(props.incidents),
  })

  for (const category of CATEGORIES) {
    const meta = CATEGORY_META[category]
    target.addLayer({
      id: `heat-${category}`,
      type: 'heatmap',
      source: 'incidents',
      filter: ['==', ['get', 'primaryCategory'], category],
      paint: {
        'heatmap-weight': ['interpolate', ['linear'], ['get', 'reports'], 1, 0.3, 8, 1],
        // Coverage area encodes severity: a critical incident heats roughly
        // 2.4x the radius of a low one, at every zoom level.
        'heatmap-radius': [
          '*',
          ['interpolate', ['linear'], ['zoom'], 11, 1, 15, 2.2],
          ['interpolate', ['linear'], ['get', 'severity'], 1, 14, 4, 34],
        ],
        'heatmap-color': [
          'interpolate',
          ['linear'],
          ['heatmap-density'],
          0,
          'rgba(0, 0, 0, 0)',
          0.25,
          meta.heatLow,
          1,
          meta.color,
        ],
        'heatmap-opacity': 0.7,
      },
    })
    target.addLayer({
      id: `points-${category}`,
      type: 'circle',
      source: 'incidents',
      filter: ['==', ['get', 'primaryCategory'], category],
      paint: {
        'circle-color': meta.color,
        'circle-radius': ['interpolate', ['linear'], ['get', 'reports'], 1, 5, 8, 12],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.5,
      },
    })
  }

  target.on('click', CATEGORIES.map((c) => `points-${c}`), (event) => {
    const feature = event.features?.[0]
    if (!feature) return
    const properties = feature.properties as Record<string, string>
    const label =
      CATEGORY_META[(properties.primaryCategory as Category) ?? 'other'].label
    new maplibregl.Popup({ closeButton: true })
      .setLngLat(event.lngLat)
      .setHTML(
        `<strong>${label}</strong><br>` +
          `${properties.reports} confirmed reports<br>` +
          `Priority: ${properties.priority}<br>` +
          `Latest: ${formatDateTime(properties.latestReportedAt)}`,
      )
      .addTo(target)
  })
}

function applyVisibility(target: maplibregl.Map): void {
  for (const category of CATEGORIES) {
    const visibility = props.visibleCategories.has(category) ? 'visible' : 'none'
    target.setLayoutProperty(`heat-${category}`, 'visibility', visibility)
    target.setLayoutProperty(`points-${category}`, 'visibility', visibility)
  }
}

onMounted(() => {
  if (!container.value) return
  map = new maplibregl.Map({
    container: container.value,
    style: BASE_STYLE,
    center: DEMO_CENTER,
    zoom: 12,
    attributionControl: { compact: false },
  })
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }))
  map.on('load', () => {
    if (!map) return
    addIncidentLayers(map)
    applyVisibility(map)
  })
})

watch(
  () => props.incidents,
  (incidents) => {
    const source = map?.getSource('incidents') as maplibregl.GeoJSONSource | undefined
    source?.setData(incidentsToGeoJson(incidents))
  },
)

watch(
  () => props.visibleCategories,
  () => {
    if (map?.isStyleLoaded()) applyVisibility(map)
  },
)

onBeforeUnmount(() => {
  map?.remove()
  map = null
})
</script>

<template>
  <div ref="container" class="map" role="application" aria-label="Confirmed incident heatmap" />
</template>

<style scoped>
.map {
  width: 100%;
  height: min(70vh, 640px);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  overflow: hidden;
}
</style>
```

- [ ] **Step 7: Write the real `src/views/MapView.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { toUserMessage } from '../api/errors'
import type { Category, IncidentSummary, PriorityLevel } from '../api/types'
import { CATEGORIES, PRIORITY_LEVELS } from '../api/types'
import IncidentMap from '../components/map/IncidentMap.vue'
import MapLegend from '../components/map/MapLegend.vue'

const incidents = ref<IncidentSummary[]>([])
const error = ref<string | null>(null)
const loading = ref(true)
const visible = ref(new Set<Category>(CATEGORIES))
const priorityFilter = ref<PriorityLevel | undefined>(undefined)

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const page = await api.listIncidents({
      status: 'confirmed',
      priority: priorityFilter.value,
      limit: 100,
    })
    incidents.value = page.items
  } catch (err) {
    error.value = toUserMessage(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="map-view">
    <header>
      <h2>Confirmed incident map</h2>
      <p class="caption">
        Each category has its own color. Heat intensity comes from confirmed reports only,
        and coverage grows with priority severity; pending candidates never appear here.
        Base map tiles need network access; incident colors still render offline.
      </p>
    </header>

    <div class="map-controls">
      <label class="field">
        <span class="field-label">Priority</span>
        <select v-model="priorityFilter" class="control" @change="load()">
          <option :value="undefined">All priorities</option>
          <option v-for="level in PRIORITY_LEVELS" :key="level" :value="level">
            {{ level }}
          </option>
        </select>
      </label>
      <MapLegend :visible="visible" @update:visible="visible = $event" />
    </div>

    <div v-if="error" class="panel-error">
      <p>{{ error }}</p>
    </div>

    <p v-else-if="loading" role="status">Loading confirmed incidents...</p>

    <p v-else-if="incidents.length === 0" class="empty">
      No confirmed incident snapshots match this filter.
    </p>

    <IncidentMap v-else :incidents="incidents" :visible-categories="visible" />
  </section>
</template>

<style scoped>
.map-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

h2 {
  font-size: 22px;
}

.caption {
  color: var(--text-secondary);
  font-size: 13px;
  max-width: 65ch;
}

.map-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
}

.empty {
  color: var(--text-secondary);
  padding: 32px 0;
  text-align: center;
}
</style>
```

- [ ] **Step 8: Verify**

Run: `npm run test -- --run` and `npm run typecheck` → all green (the MapLibre component has no jsdom test; the projection and severity logic are covered by the pure-function tests).
Run: `npm run dev` with the API running → map centers on the district, per-category heat blobs render in distinct colors, a critical incident visibly covers more area than a low one, the priority filter narrows the map, clicking a point opens a popup, unchecking a legend category hides its layers.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src
git commit -m "feat(frontend): MapLibre incident map with per-category heatmap and legend"
```

---

### Task 9: Submit report form with photo evidence

**Files:**
- Create: `frontend/src/components/submit/photo.ts`
- Modify: `frontend/src/views/SubmitView.vue` (replace placeholder)
- Test: `frontend/src/components/submit/photo.test.ts`
- Test: `frontend/src/views/SubmitView.test.ts`

**Interfaces:**
- Consumes: `api.submitComplaint(body, idempotencyKey)`, `CATEGORY_META`, `IncidentSummaryRow`, `exifr`
- Produces: a working submission flow with photo evidence. `validatePhoto(file: File): { ok: boolean; error?: string }` (JPEG/PNG, max 8 MB) and `extractPhotoGps(file: File): Promise<{ latitude: number; longitude: number } | null>` in `photo.ts`. Attaching a photo prefills coordinates from EXIF GPS when present and sends `photo_path` (the file name) in the complaint body; the server's priority policy counts this as evidence completeness ("N/M confirmed reports include photos"). The Idempotency-Key is generated once per form instance with `crypto.randomUUID()`, reused across retries of the same submission, and regenerated only after a success, so accidental double-clicks replay instead of duplicating.

**Boundary note (frozen contract):** the API v1 contract has no photo upload or analysis endpoint; `photo_path` is a string field and the photo provider healthcheck reports "not configured" by default. In v1 the image bytes stay on the operator's device: the interface captures the photo, extracts its GPS metadata locally, previews it, and records the evidence reference. Server-side storage and processing require a new multipart endpoint plus an explicit OpenAPI snapshot update; that is a documented follow-up phase, not part of this plan. The UI must say this honestly next to the upload control.

- [ ] **Step 1: Write the failing photo helper test `src/components/submit/photo.test.ts`**

```ts
import { describe, expect, it, vi } from 'vitest'

const gps = vi.fn()
vi.mock('exifr', () => ({ default: { gps: (...a: unknown[]) => gps(...a) } }))

import { extractPhotoGps, validatePhoto, MAX_PHOTO_BYTES } from './photo'

function fakeFile(type: string, size: number): File {
  const file = new File(['x'], 'evidence.jpg', { type })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

describe('validatePhoto', () => {
  it('accepts a small JPEG', () => {
    expect(validatePhoto(fakeFile('image/jpeg', 1024))).toEqual({ ok: true })
  })

  it('rejects unsupported types with a plain instruction', () => {
    const result = validatePhoto(fakeFile('application/pdf', 1024))
    expect(result.ok).toBe(false)
    expect(result.error).toContain('JPEG or PNG')
  })

  it('rejects oversized files', () => {
    const result = validatePhoto(fakeFile('image/png', MAX_PHOTO_BYTES + 1))
    expect(result.ok).toBe(false)
    expect(result.error).toContain('8 MB')
  })
})

describe('extractPhotoGps', () => {
  it('returns coordinates when EXIF GPS is present', async () => {
    gps.mockResolvedValue({ latitude: 3.082, longitude: 101.52 })
    await expect(extractPhotoGps(fakeFile('image/jpeg', 10))).resolves.toEqual({
      latitude: 3.082,
      longitude: 101.52,
    })
  })

  it('returns null when EXIF is missing or unreadable', async () => {
    gps.mockRejectedValue(new Error('no exif'))
    await expect(extractPhotoGps(fakeFile('image/jpeg', 10))).resolves.toBeNull()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/components/submit/photo.test.ts`
Expected: FAIL, `./photo` not found.

- [ ] **Step 3: Write `src/components/submit/photo.ts`**

```ts
import exifr from 'exifr'

export const MAX_PHOTO_BYTES = 8 * 1024 * 1024

const ALLOWED_TYPES = ['image/jpeg', 'image/png']

export interface PhotoValidation {
  ok: boolean
  error?: string
}

export function validatePhoto(file: File): PhotoValidation {
  if (!ALLOWED_TYPES.includes(file.type)) {
    return { ok: false, error: 'Use a JPEG or PNG photo.' }
  }
  if (file.size > MAX_PHOTO_BYTES) {
    return { ok: false, error: 'Keep the photo under 8 MB.' }
  }
  return { ok: true }
}

export interface PhotoGps {
  latitude: number
  longitude: number
}

export async function extractPhotoGps(file: File): Promise<PhotoGps | null> {
  try {
    const gps = await exifr.gps(file)
    if (gps && Number.isFinite(gps.latitude) && Number.isFinite(gps.longitude)) {
      return { latitude: gps.latitude, longitude: gps.longitude }
    }
  } catch {
    // A photo without readable EXIF is normal, not an error.
  }
  return null
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npm run test -- --run src/components/submit/photo.test.ts`
Expected: 5 passed.

- [ ] **Step 5: Write the failing view test `src/views/SubmitView.test.ts`**

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

const submitComplaint = vi.fn()
vi.mock('../api', () => ({
  api: { submitComplaint: (...a: unknown[]) => submitComplaint(...a) },
}))
vi.mock('exifr', () => ({ default: { gps: vi.fn().mockResolvedValue(null) } }))

import SubmitView from './SubmitView.vue'

function fill(wrapper: ReturnType<typeof mount>) {
  return Promise.all([
    wrapper.get('#report-text').setValue('Longkang tersumbat depan sekolah, air melimpah'),
    wrapper.get('#report-lat').setValue('3.082'),
    wrapper.get('#report-lng').setValue('101.52'),
  ])
}

describe('SubmitView', () => {
  beforeEach(() => submitComplaint.mockReset())

  it('reuses the same idempotency key across a retry of the same submission', async () => {
    submitComplaint.mockRejectedValueOnce(new Error('network'))
    submitComplaint.mockResolvedValueOnce({
      complaint: { complaint_id: 'c1' },
      created: true,
      replayed: false,
      relationship_decisions: [],
      incident_transition: { previous_incident_snapshot_ids: [], current_incident_snapshot_ids: [] },
      incidents: [],
      priorities: [],
    })
    const wrapper = mount(SubmitView, { global: { plugins: [createPinia()] } })
    await fill(wrapper)
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(submitComplaint).toHaveBeenCalledTimes(1))
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(submitComplaint).toHaveBeenCalledTimes(2))
    const firstKey = submitComplaint.mock.calls[0][1]
    const secondKey = submitComplaint.mock.calls[1][1]
    expect(firstKey).toBe(secondKey)
  })

  it('blocks invalid text without calling the API', async () => {
    const wrapper = mount(SubmitView, { global: { plugins: [createPinia()] } })
    await wrapper.get('#report-text').setValue('ab')
    await wrapper.get('form').trigger('submit')
    expect(submitComplaint).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('at least 3 characters')
  })
})
```

- [ ] **Step 6: Run to verify failure**

Run: `npm run test -- --run src/views/SubmitView.test.ts`
Expected: FAIL (placeholder view has no form).

- [ ] **Step 7: Write the real `src/views/SubmitView.vue`**

```vue
<script setup lang="ts">
import { onBeforeUnmount, reactive, ref } from 'vue'
import { api } from '../api'
import { toUserMessage } from '../api/errors'
import type { Category, ComplaintSubmissionResponse } from '../api/types'
import { CATEGORIES } from '../api/types'
import { CATEGORY_META } from '../domain/categories'
import { extractPhotoGps, validatePhoto } from '../components/submit/photo'
import IncidentSummaryRow from '../components/incidents/IncidentSummaryRow.vue'

const form = reactive({
  text: '',
  category: '' as Category | '',
  latitude: '3.07000',
  longitude: '101.52000',
})

const errors = reactive<{ text?: string; latitude?: string; longitude?: string }>({})
const submitting = ref(false)
const submitError = ref<string | null>(null)
const result = ref<ComplaintSubmissionResponse | null>(null)

const photoFile = ref<File | null>(null)
const photoPreviewUrl = ref<string | null>(null)
const photoError = ref<string | null>(null)
const gpsFromPhoto = ref(false)

/** One key per logical submission; regenerated only after success. */
let idempotencyKey = crypto.randomUUID()

function clearPhoto(): void {
  if (photoPreviewUrl.value) URL.revokeObjectURL(photoPreviewUrl.value)
  photoFile.value = null
  photoPreviewUrl.value = null
  photoError.value = null
  gpsFromPhoto.value = false
}

async function onPhotoChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  clearPhoto()
  if (!file) return
  const validation = validatePhoto(file)
  if (!validation.ok) {
    photoError.value = validation.error ?? 'That photo cannot be used.'
    input.value = ''
    return
  }
  photoFile.value = file
  photoPreviewUrl.value = URL.createObjectURL(file)
  const gps = await extractPhotoGps(file)
  if (gps) {
    form.latitude = gps.latitude.toFixed(5)
    form.longitude = gps.longitude.toFixed(5)
    gpsFromPhoto.value = true
  }
}

onBeforeUnmount(clearPhoto)

function validate(): boolean {
  errors.text =
    form.text.trim().length < 3
      ? 'Describe the problem in at least 3 characters.'
      : form.text.length > 2000
        ? 'Keep the description under 2000 characters.'
        : undefined
  const lat = Number(form.latitude)
  errors.latitude =
    Number.isFinite(lat) && lat >= -90 && lat <= 90
      ? undefined
      : 'Latitude must be between -90 and 90.'
  const lng = Number(form.longitude)
  errors.longitude =
    Number.isFinite(lng) && lng >= -180 && lng <= 180
      ? undefined
      : 'Longitude must be between -180 and 180.'
  return !errors.text && !errors.latitude && !errors.longitude
}

async function submit(): Promise<void> {
  submitError.value = null
  if (!validate() || submitting.value) return
  submitting.value = true
  try {
    result.value = await api.submitComplaint(
      {
        text: form.text.trim(),
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        reported_at: new Date().toISOString(),
        category: form.category === '' ? null : form.category,
        photo_path: photoFile.value ? photoFile.value.name : null,
      },
      idempotencyKey,
    )
    idempotencyKey = crypto.randomUUID()
    form.text = ''
    form.category = ''
    clearPhoto()
  } catch (err) {
    submitError.value = toUserMessage(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="submit-view">
    <header>
      <h2>Submit report</h2>
      <p class="caption">
        New reports go through the same matching pipeline as seeded complaints. Retrying the
        same submission is safe; the API replays it instead of creating a duplicate.
      </p>
    </header>

    <form class="report-form" novalidate @submit.prevent="submit">
      <div class="field">
        <label class="field-label" for="report-text">What is the problem?</label>
        <textarea
          id="report-text"
          v-model="form.text"
          class="control"
          rows="4"
          maxlength="2000"
          :aria-invalid="Boolean(errors.text)"
        />
        <p class="field-help">Plain language is fine, in any local language.</p>
        <p v-if="errors.text" class="field-error">{{ errors.text }}</p>
      </div>

      <div class="field">
        <label class="field-label" for="report-category">Category (optional)</label>
        <select id="report-category" v-model="form.category" class="control">
          <option value="">Let the system categorize it</option>
          <option v-for="category in CATEGORIES" :key="category" :value="category">
            {{ CATEGORY_META[category].label }}
          </option>
        </select>
      </div>

      <div class="field">
        <label class="field-label" for="report-photo">Photo (optional)</label>
        <input
          id="report-photo"
          type="file"
          accept="image/jpeg,image/png"
          class="control"
          @change="onPhotoChange"
        />
        <p class="field-help">
          Photo evidence raises the incident's evidence completeness. The image stays on this
          device in the current prototype; only the evidence reference is recorded.
        </p>
        <p v-if="photoError" class="field-error">{{ photoError }}</p>
        <div v-if="photoPreviewUrl" class="photo-preview">
          <img :src="photoPreviewUrl" alt="Selected report photo" />
          <div class="photo-preview-meta">
            <span class="mono">{{ photoFile?.name }}</span>
            <p v-if="gpsFromPhoto" class="field-help">Coordinates filled from the photo's GPS data.</p>
            <button type="button" class="button-secondary" @click="clearPhoto">Remove photo</button>
          </div>
        </div>
      </div>

      <div class="coords">
        <div class="field">
          <label class="field-label" for="report-lat">Latitude</label>
          <input
            id="report-lat"
            v-model="form.latitude"
            class="control mono"
            inputmode="decimal"
            :aria-invalid="Boolean(errors.latitude)"
          />
          <p v-if="errors.latitude" class="field-error">{{ errors.latitude }}</p>
        </div>
        <div class="field">
          <label class="field-label" for="report-lng">Longitude</label>
          <input
            id="report-lng"
            v-model="form.longitude"
            class="control mono"
            inputmode="decimal"
            :aria-invalid="Boolean(errors.longitude)"
          />
          <p v-if="errors.longitude" class="field-error">{{ errors.longitude }}</p>
        </div>
      </div>
      <p class="field-help">
        Defaults point at the synthetic demo district. Copy coordinates from the map view for
        a specific spot.
      </p>

      <div v-if="submitError" class="panel-error">
        <p>{{ submitError }}</p>
      </div>

      <button type="submit" class="button-primary" :disabled="submitting">
        {{ submitting ? 'Submitting report...' : 'Submit report' }}
      </button>
    </form>

    <section v-if="result" class="result" aria-live="polite">
      <h3>{{ result.replayed ? 'Report already recorded' : 'Report recorded' }}</h3>
      <p class="caption">
        {{
          result.replayed
            ? 'This submission matched an earlier one and was replayed, not duplicated.'
            : 'The matching pipeline processed this report.'
        }}
      </p>

      <div v-if="result.relationship_decisions.length > 0" class="decisions">
        <h4>Matcher decisions</h4>
        <ul>
          <li v-for="edge in result.relationship_decisions" :key="`${edge.left_id}-${edge.right_id}`">
            <strong>{{ edge.decision.replace('_', ' ') }}</strong>
            <ul>
              <li v-for="reason in edge.reasons" :key="reason">{{ reason }}</li>
            </ul>
          </li>
        </ul>
      </div>

      <div v-if="result.incidents.length > 0" class="decisions">
        <h4>Affected incidents</h4>
        <ul class="incident-list">
          <li v-for="incident in result.incidents" :key="incident.incident_id">
            <IncidentSummaryRow :incident="incident" />
          </li>
        </ul>
      </div>
    </section>
  </section>
</template>

<style scoped>
.submit-view {
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

h2 {
  font-size: 22px;
}

.caption {
  color: var(--text-secondary);
  font-size: 13px;
}

.report-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
}

.coords {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.photo-preview {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 10px;
  background: var(--surface-sunken);
  border-radius: var(--radius-control);
}

.photo-preview img {
  max-width: 160px;
  max-height: 120px;
  border-radius: var(--radius-control);
  object-fit: cover;
}

.photo-preview-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.result {
  padding: 16px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result h3 {
  font-size: 16px;
}

.decisions h4 {
  font-size: 14px;
  margin-bottom: 6px;
}

.decisions ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--text-secondary);
}

.incident-list {
  list-style: none;
  padding: 0 !important;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 640px) {
  .coords {
    grid-template-columns: 1fr;
  }
}
</style>
```

- [ ] **Step 8: Run to verify pass**

Run: `npm run test -- --run src/views/SubmitView.test.ts`
Expected: 2 passed. (jsdom ships `crypto.randomUUID`; if the environment lacks it, stub it in the test with `vi.stubGlobal`.)

- [ ] **Step 9: Verify against the live API**

Run: `npm run dev` with the API running. Submit the runbook's Manglish example ("Longkang tersumbat depan sekolah...") near `3.082, 101.52` → outcome panel shows a `review_required` matcher decision with reasons. Attach a JPEG with GPS EXIF → coordinates prefill and the preview renders; attach a PDF → inline "Use a JPEG or PNG photo." error; submit with a photo → the complaint carries `photo_path` (confirm in the API response panel).

- [ ] **Step 10: Commit**

```powershell
git add frontend/src/views/SubmitView.vue frontend/src/views/SubmitView.test.ts frontend/src/components/submit
git commit -m "feat(frontend): complaint submission with photo evidence and idempotent retry"
```

---

### Task 10: Review queue with evidence and resolution

**Files:**
- Create: `frontend/src/stores/reviews.ts`
- Create: `frontend/src/components/reviews/ReviewSummaryRow.vue`
- Create: `frontend/src/components/reviews/ReviewEvidencePanel.vue`
- Modify: `frontend/src/views/ReviewsView.vue` (replace placeholder)
- Test: `frontend/src/stores/reviews.test.ts`

**Interfaces:**
- Consumes: `api.listReviews`, `api.getReview`, `api.approveReview`, `api.rejectReview`, `AccordionCard`, formatters, `CategoryChip`
- Produces: `useReviewsStore()` with `items: ReviewSummary[]`, `statusFilter: 'pending' | 'approved' | 'rejected'`, `load()`, `loadDetail(id)`, `detailFor(id)`, `resolve(id, action: 'approve' | 'reject', body): Promise<ReviewMutationResponse | null>`, `lastResolution: ReviewMutationResponse | null`. After a resolution the list reloads (resolved reviews leave the pending filter) and the incidents store cache is stale, so `resolve` also calls `useIncidentsStore().load()`.

- [ ] **Step 1: Write the failing store test `src/stores/reviews.test.ts`**

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const listReviews = vi.fn()
const getReview = vi.fn()
const approveReview = vi.fn()
const listIncidents = vi.fn()
vi.mock('../api', () => ({
  api: {
    listReviews: (...a: unknown[]) => listReviews(...a),
    getReview: (...a: unknown[]) => getReview(...a),
    approveReview: (...a: unknown[]) => approveReview(...a),
    rejectReview: vi.fn(),
    listIncidents: (...a: unknown[]) => listIncidents(...a),
    getIncident: vi.fn(),
  },
}))

import { useReviewsStore } from './reviews'

describe('reviews store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listReviews.mockReset()
    approveReview.mockReset()
    listIncidents.mockResolvedValue({ items: [], limit: 50, offset: 0, total: 0 })
  })

  it('loads pending reviews by default', async () => {
    listReviews.mockResolvedValue({ items: [], limit: 50, offset: 0, total: 0 })
    const store = useReviewsStore()
    await store.load()
    expect(listReviews).toHaveBeenCalledWith({ status: 'pending', limit: 50, offset: 0 })
  })

  it('approve resolves, stores the mutation result, and reloads the list', async () => {
    listReviews.mockResolvedValue({ items: [], limit: 50, offset: 0, total: 0 })
    approveReview.mockResolvedValue({ final_relationship_state: 'auto_match' })
    const store = useReviewsStore()
    const outcome = await store.resolve('r1', 'approve', { reviewer_id: 'officer-1', note: null })
    expect(approveReview).toHaveBeenCalledWith('r1', { reviewer_id: 'officer-1', note: null })
    expect(outcome).not.toBeNull()
    expect(store.lastResolution).not.toBeNull()
    expect(listReviews).toHaveBeenCalled()
  })

  it('captures resolution errors without clearing the queue', async () => {
    listReviews.mockResolvedValue({ items: [], limit: 50, offset: 0, total: 0 })
    approveReview.mockRejectedValue(new Error('stale'))
    const store = useReviewsStore()
    const outcome = await store.resolve('r1', 'approve', { reviewer_id: 'officer-1', note: null })
    expect(outcome).toBeNull()
    expect(store.resolveError).not.toBeNull()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/stores/reviews.test.ts`
Expected: FAIL, module not found.

- [ ] **Step 3: Write `src/stores/reviews.ts`**

```ts
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { api } from '../api'
import { toUserMessage } from '../api/errors'
import type {
  ReviewDetail,
  ReviewMutationResponse,
  ReviewResolutionRequest,
  ReviewSummary,
} from '../api/types'
import { useIncidentsStore } from './incidents'

export type ReviewStatusFilter = 'pending' | 'approved' | 'rejected'

export const useReviewsStore = defineStore('reviews', () => {
  const items = ref<ReviewSummary[]>([])
  const total = ref(0)
  const statusFilter = ref<ReviewStatusFilter>('pending')
  const loading = ref(false)
  const error = ref<string | null>(null)

  const details = reactive(new Map<string, ReviewDetail>())
  const detailErrors = reactive(new Map<string, string>())

  const resolving = ref(false)
  const resolveError = ref<string | null>(null)
  const lastResolution = ref<ReviewMutationResponse | null>(null)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const page = await api.listReviews({ status: statusFilter.value, limit: 50, offset: 0 })
      items.value = page.items
      total.value = page.total
    } catch (err) {
      error.value = toUserMessage(err)
      items.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  async function loadDetail(reviewId: string): Promise<void> {
    if (details.has(reviewId)) return
    detailErrors.delete(reviewId)
    try {
      details.set(reviewId, await api.getReview(reviewId))
    } catch (err) {
      detailErrors.set(reviewId, toUserMessage(err))
    }
  }

  async function resolve(
    reviewId: string,
    action: 'approve' | 'reject',
    body: ReviewResolutionRequest,
  ): Promise<ReviewMutationResponse | null> {
    resolving.value = true
    resolveError.value = null
    try {
      const outcome =
        action === 'approve'
          ? await api.approveReview(reviewId, body)
          : await api.rejectReview(reviewId, body)
      lastResolution.value = outcome
      details.delete(reviewId)
      await load()
      await useIncidentsStore().load()
      return outcome
    } catch (err) {
      resolveError.value = toUserMessage(err)
      return null
    } finally {
      resolving.value = false
    }
  }

  const detailFor = (id: string): ReviewDetail | undefined => details.get(id)
  const detailError = (id: string): string | undefined => detailErrors.get(id)

  return {
    items,
    total,
    statusFilter,
    loading,
    error,
    load,
    loadDetail,
    detailFor,
    detailError,
    resolve,
    resolving,
    resolveError,
    lastResolution,
  }
})
```

- [ ] **Step 4: Run to verify pass**

Run: `npm run test -- --run src/stores/reviews.test.ts`
Expected: 3 passed.

- [ ] **Step 5: Write `src/components/reviews/ReviewSummaryRow.vue`**

```vue
<script setup lang="ts">
import type { ReviewSummary } from '../../api/types'
import { formatDateTime } from '../../domain/format'

defineProps<{ review: ReviewSummary }>()
</script>

<template>
  <div class="row">
    <div class="row-main">
      <span class="recommendation">
        Matcher says: <strong>{{ review.original_matcher_recommendation.replace('_', ' ') }}</strong>
      </span>
      <span class="row-status" :data-status="review.status">{{ review.status }}</span>
    </div>
    <span class="row-time">Created {{ formatDateTime(review.created_at) }}</span>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
}

.row-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.recommendation {
  font-size: 14px;
}

.row-status {
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
  background: var(--surface-sunken);
  color: var(--text-secondary);
}

.row-status[data-status='approved'] {
  background: var(--status-confirmed-bg);
  color: var(--status-confirmed-text);
}

.row-status[data-status='rejected'] {
  background: var(--status-conflict-bg);
  color: var(--status-conflict-text);
}

.row-time {
  color: var(--text-muted);
  font-size: 13px;
}
</style>
```

- [ ] **Step 6: Write `src/components/reviews/ReviewEvidencePanel.vue`**

```vue
<script setup lang="ts">
import type { ReviewDetail } from '../../api/types'
import {
  formatCoords,
  formatDateTime,
  formatDuration,
  formatMetres,
  formatPercent,
} from '../../domain/format'
import CategoryChip from '../CategoryChip.vue'

defineProps<{ detail: ReviewDetail }>()
</script>

<template>
  <div class="evidence">
    <div class="pair">
      <article
        v-for="complaint in [detail.complaint_a, detail.complaint_b]"
        :key="complaint.complaint_id"
        class="complaint"
      >
        <p class="complaint-text">{{ complaint.text }}</p>
        <p class="complaint-meta">
          <CategoryChip :category="complaint.category" />
          <span class="mono">{{ formatCoords(complaint.latitude, complaint.longitude) }}</span>
          <span>{{ formatDateTime(complaint.reported_at) }}</span>
        </p>
      </article>
    </div>

    <dl v-if="detail.matcher_evidence" class="metrics">
      <div class="metric">
        <dt>Text similarity</dt>
        <dd class="mono">{{ formatPercent(detail.matcher_evidence.semantic_similarity) }}</dd>
      </div>
      <div class="metric">
        <dt>Distance apart</dt>
        <dd class="mono">{{ formatMetres(detail.matcher_evidence.geo_distance_metres) }}</dd>
      </div>
      <div class="metric">
        <dt>Time apart</dt>
        <dd class="mono">{{ formatDuration(detail.matcher_evidence.time_difference_seconds) }}</dd>
      </div>
      <div class="metric">
        <dt>Same category</dt>
        <dd>{{ detail.matcher_evidence.category_compatibility ? 'Yes' : 'No' }}</dd>
      </div>
      <div class="metric">
        <dt>Locations</dt>
        <dd>{{ detail.matcher_evidence.location_compatibility }}</dd>
      </div>
    </dl>

    <section class="reasons">
      <h4>Why the matcher asked for review</h4>
      <ul>
        <li v-for="reason in detail.matcher_reasons" :key="reason">{{ reason }}</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.evidence {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.complaint {
  padding: 12px;
  background: var(--surface-sunken);
  border-radius: var(--radius-control);
}

.complaint-text {
  font-size: 14px;
  margin-bottom: 8px;
}

.complaint-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 8px 16px;
  margin: 0;
}

.metric dt {
  font-size: 12px;
  color: var(--text-muted);
}

.metric dd {
  margin: 0;
  font-size: 14px;
}

.reasons h4 {
  font-size: 14px;
  margin-bottom: 6px;
}

.reasons ul {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 640px) {
  .pair {
    grid-template-columns: 1fr;
  }
}
</style>
```

- [ ] **Step 7: Write the real `src/views/ReviewsView.vue`**

```vue
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useReviewsStore } from '../stores/reviews'
import AccordionCard from '../components/AccordionCard.vue'
import ReviewSummaryRow from '../components/reviews/ReviewSummaryRow.vue'
import ReviewEvidencePanel from '../components/reviews/ReviewEvidencePanel.vue'
import IncidentSummaryRow from '../components/incidents/IncidentSummaryRow.vue'

const store = useReviewsStore()
const expandedId = ref<string | null>(null)
const resolution = reactive({ reviewerId: '', note: '' })
const reviewerError = ref<string | null>(null)

onMounted(() => store.load())

function toggle(reviewId: string): void {
  expandedId.value = expandedId.value === reviewId ? null : reviewId
  if (expandedId.value) void store.loadDetail(reviewId)
}

async function act(reviewId: string, action: 'approve' | 'reject'): Promise<void> {
  if (resolution.reviewerId.trim().length === 0) {
    reviewerError.value = 'Enter your reviewer ID before deciding.'
    return
  }
  reviewerError.value = null
  const outcome = await store.resolve(reviewId, action, {
    reviewer_id: resolution.reviewerId.trim(),
    note: resolution.note.trim() === '' ? null : resolution.note.trim(),
  })
  if (outcome) expandedId.value = null
}
</script>

<template>
  <section class="reviews-view">
    <header>
      <h2>Review queue</h2>
      <p class="caption">
        The matcher sends uncertain pairs here instead of guessing. Your decision becomes the
        recorded relationship.
      </p>
    </header>

    <div class="toolbar">
      <label class="field">
        <span class="field-label">Show</span>
        <select v-model="store.statusFilter" class="control" @change="store.load()">
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </label>
      <p class="mono total" aria-live="polite">{{ store.total }} reviews</p>
    </div>

    <div v-if="store.lastResolution" class="resolution-summary" aria-live="polite">
      <h3>Decision recorded</h3>
      <p>
        Final relationship:
        <strong>{{ store.lastResolution.final_relationship_state.replace('_', ' ') }}</strong>
      </p>
      <ul v-if="store.lastResolution.affected_incidents.length > 0" class="incident-list">
        <li v-for="incident in store.lastResolution.affected_incidents" :key="incident.incident_id">
          <IncidentSummaryRow :incident="incident" />
        </li>
      </ul>
    </div>

    <div v-if="store.error" class="panel-error">
      <p>{{ store.error }}</p>
      <button type="button" class="button-secondary" @click="store.load()">Retry</button>
    </div>

    <p v-else-if="store.loading" role="status">Loading reviews...</p>

    <p v-else-if="store.items.length === 0" class="empty">
      No {{ store.statusFilter }} reviews right now.
    </p>

    <ul v-else class="review-list">
      <li v-for="review in store.items" :key="review.review_id">
        <AccordionCard
          :expanded="expandedId === review.review_id"
          @toggle="toggle(review.review_id)"
        >
          <template #summary>
            <ReviewSummaryRow :review="review" />
          </template>

          <p v-if="store.detailError(review.review_id)" class="field-error">
            {{ store.detailError(review.review_id) }}
          </p>
          <template v-else-if="store.detailFor(review.review_id)">
            <ReviewEvidencePanel :detail="store.detailFor(review.review_id)!" />

            <form
              v-if="review.status === 'pending'"
              class="resolution-form"
              @submit.prevent
            >
              <div class="field">
                <label class="field-label" :for="`reviewer-${review.review_id}`">Reviewer ID</label>
                <input
                  :id="`reviewer-${review.review_id}`"
                  v-model="resolution.reviewerId"
                  class="control"
                  :aria-invalid="Boolean(reviewerError)"
                />
                <p v-if="reviewerError" class="field-error">{{ reviewerError }}</p>
              </div>
              <div class="field">
                <label class="field-label" :for="`note-${review.review_id}`">Note (optional)</label>
                <input :id="`note-${review.review_id}`" v-model="resolution.note" class="control" />
              </div>
              <div v-if="store.resolveError" class="panel-error">
                <p>{{ store.resolveError }}</p>
              </div>
              <div class="actions">
                <button
                  type="button"
                  class="button-primary"
                  :disabled="store.resolving"
                  @click="act(review.review_id, 'approve')"
                >
                  Approve match
                </button>
                <button
                  type="button"
                  class="button-secondary"
                  :disabled="store.resolving"
                  @click="act(review.review_id, 'reject')"
                >
                  Reject match
                </button>
              </div>
            </form>
          </template>
          <p v-else role="status">Loading review evidence...</p>
        </AccordionCard>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.reviews-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

h2 {
  font-size: 22px;
}

.caption {
  color: var(--text-secondary);
  font-size: 13px;
}

.toolbar {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
}

.total {
  color: var(--text-secondary);
}

.resolution-summary {
  padding: 14px 16px;
  background: var(--status-confirmed-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
}

.resolution-summary h3 {
  font-size: 15px;
  color: var(--status-confirmed-text);
}

.incident-list {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.resolution-form {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.actions {
  display: flex;
  gap: 10px;
}

.empty {
  color: var(--text-secondary);
  padding: 32px 0;
  text-align: center;
}
</style>
```

- [ ] **Step 8: Verify**

Run: `npm run test -- --run` and `npm run typecheck` → all green.
Run: `npm run dev` with the API running → submit the Manglish example from Task 9, open Reviews, expand the pending card, read side-by-side complaints and evidence metrics, approve with a reviewer ID → decision summary shows the confirmed incident; the queue view reflects the change.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src
git commit -m "feat(frontend): review queue with matcher evidence and officer resolution"
```

---

### Task 11: Pre-flight audit, docs, and final verification

**Files:**
- Modify: any files failing the audit below
- Modify: `README.md` (repo root; add the Vue frontend run instructions)
- Modify: `frontend/src/App.test.ts` if the shell changed

**Interfaces:**
- Consumes: everything above
- Produces: a documented, verified, demo-runnable frontend.

- [ ] **Step 1: Run the design pre-flight audit and fix violations**

Check each item against the running app and the source; fix inline:

- Zero em-dash (`—`) or en-dash separator characters in any template string: run `Select-String -Path frontend/src -Pattern '[–—]' -Recurse` → expect no matches.
- One accent (`--accent`) for all interactive elements; category colors appear only as data encoding (dots, edges, map layers, swatches).
- Shape lock: cards 8px, controls 6px, chips pill; no strays.
- Every list view has loading, empty, and error states (queue, map, reviews, submit outcome).
- Keyboard walk: tab through nav, filters, accordions, forms; focus ring visible everywhere; accordions toggle with Enter/Space.
- `prefers-reduced-motion: reduce` (emulate in devtools): accordion and chevron snap instantly.
- Contrast spot-check: badge tint pairs and `--text-secondary` on `--surface-sunken` pass WCAG AA (use devtools contrast checker).
- Mobile at 375px wide: nav wraps cleanly, filter bar stacks, evidence pair stacks to one column, map stays usable.
- Minimalism sweep: no icon library in `package.json`, no decorative elements, every visible element maps to an operator task; remove anything that fails this test.
- Map severity check: with the seed loaded, a critical incident's heat blob is visibly larger than a low one at the same zoom; the priority filter narrows the map.
- Photo hygiene: preview object URLs are revoked on remove, replace, submit, and unmount (watch the Memory panel for leaked blobs); the "image stays on this device" caption is present.
- Copy self-audit: read every visible string once; plain sentences, no AI-flavored phrasing, the synthetic-data notice present in the footer.

- [ ] **Step 2: Add frontend instructions to the root `README.md`**

Add under the Dashboard section (keep the Streamlit instructions intact):

```markdown
### Vue frontend (new operator UI)

The Vue 3 frontend in `frontend/` is an HTTP client of the same `/api/v1` contract.

```powershell
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to `http://127.0.0.1:8000`, so start the composed API first.
Verification: `npm run test -- --run`, `npm run typecheck`, `npm run build`.
```

- [ ] **Step 3: Full verification**

Run and record actual output:

```powershell
cd frontend
npm run test -- --run
npm run typecheck
npm run build
```

Expected: all Vitest suites pass, vue-tsc reports 0 errors, production build succeeds.

Backend regression guard (nothing under `src/` changed):

```powershell
git status --short src tests
```

Expected: empty.

Live demo walk (API running): queue loads seeded incidents → filter by flooding → expand a card → open map, toggle categories, click a point → submit the Manglish report → approve it in Reviews → queue shows the new confirmed incident.

- [ ] **Step 4: Commit**

```powershell
git add README.md frontend
git commit -m "docs(frontend): document Vue operator UI and complete pre-flight audit"
```

---

## Self-Review

- **Spec coverage:** Vue 3 + TypeScript (Tasks 1 to 11), taste-skill + frontend-design discipline (Design Read, tokens, pre-flight audit in Task 11), white/neutral government palette (Task 1 tokens, light-only lock), minimalism as a hard rule (design section, Global Constraints, Task 11 sweep; no icon library, no tagline, no ornament), per-category colored heatmap (Task 8, MapLibre GL with one tinted heatmap + circle layer pair per category), severity-scaled heat coverage plus a map priority filter (Task 8: `severityRank`, data-driven `heatmap-radius`, MapView filter), photo upload and processing interface within the frozen contract (Task 9: validation, preview, EXIF GPS extraction, `photo_path` evidence that the server's priority policy counts; server-side storage documented as follow-up), accordion cards for event records (Task 5 base component, used for incidents in Task 6 and reviews in Task 10), first-time-user simplicity (readiness gate with recovery text, plain-language captions, one accent, legend with toggles, explicit empty/error states). Parity with the Streamlit dashboard: queue, detail, map, submit, reviews all covered; safe reset explicitly deferred (non-goal, server flag off by default).
- **Placeholder scan:** the only intentional placeholder is Task 6's temporary detail body, which Task 7 explicitly replaces; all other steps carry complete code.
- **Type consistency:** `detailFor`/`detailError`/`isDetailLoading` names match between the incidents store (Task 6) and QueueView (Tasks 6/7); `resolve`/`lastResolution` match between the reviews store and ReviewsView (Task 10); `CATEGORY_META.heatLow` defined in Task 3 and consumed in Task 8; `severityRank` defined and tested in Task 8's `geojson.ts` and consumed by both the feature properties and the `heatmap-radius` expression; `validatePhoto`/`extractPhotoGps` signatures match between `photo.ts` and SubmitView; `IncidentSummaryRow` props identical across queue, submit outcome, and resolution summary usages.
