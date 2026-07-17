# Online Street Map and Control Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blank local map style with an online OpenFreeMap street map, make density/selection overlays legible, and restyle raw-looking submission controls.

**Architecture:** The MapLibre adapter continues to own map infrastructure and receives an online style URL as its default. `IncidentMapPanel` owns only filter, legend, lifecycle, and intent UI. `SubmitPage` keeps native semantic controls but applies explicit CivicPulse variants; no component library or API change is introduced.

**Tech Stack:** Vue 3, TypeScript 5.9, MapLibre GL 5.24, Vitest, Vue Test Utils, scoped CSS, Playwright CLI.

## Global Constraints

- Use `https://tiles.openfreemap.org/styles/liberty` directly; do not add an API key or offline fallback.
- Never include complaint text, review data, photo identifiers, or incident membership in basemap requests.
- Density colors are exactly `#2F80ED`, `#22B8A7`, `#F2C94C`, `#F2994A`, and `#D64545` from low to high.
- Density is presentation-only; do not alter server-owned matching, clustering, priority, incident ordering, or heat-cell aggregation.
- Keep all MapLibre objects/listeners/cleanup in `maplibre-map-adapter.ts`.
- Preserve semantic `button`, `label`, `input[type=file]`, keyboard behavior, visible focus, and reduced-motion support.
- Interactive controls must reach at least 44 px height on touch layouts.
- Use existing CivicPulse tokens and typography; add no frontend dependency.
- Run all frontend commands inside `frontend/` with pnpm 11.9.0.

---

### Task 1: Online street style and density overlay contract

**Files:**
- Modify: `frontend/src/features/incidents/adapters/map/maplibre-map-adapter.ts`
- Test: `frontend/src/features/incidents/adapters/map/maplibre-map-adapter.spec.ts`

**Interfaces:**
- Consumes: existing `MapFactoryOptions`, `MapLibreIncidentMapRendererOptions.style`, `IncidentMapView`, and `MapLifecycleState`.
- Produces: exported `OPENFREEMAP_STYLE_URL`, online default style, attribution-enabled map options, fixed density gradient, and outlined selected point.

- [ ] **Step 1: Write failing adapter assertions**

Extend the existing map factory test so it captures `MapFactoryOptions` and asserts the online default and attribution:

```ts
import {
  createMapLibreIncidentMapRenderer,
  OPENFREEMAP_STYLE_URL,
  type MapFactoryOptions,
} from "./maplibre-map-adapter"

it("uses the OpenFreeMap street style with attribution by default", () => {
  let options: MapFactoryOptions | undefined
  const renderer = createMapLibreIncidentMapRenderer({
    createMap: (candidate) => {
      options = candidate
      return mapLike({ styleLoaded: true })
    },
  })

  renderer.mount(document.createElement("div"))

  expect(options?.style).toBe(OPENFREEMAP_STYLE_URL)
  expect(options?.attributionControl).toBe(true)
})
```

In the existing rendered-layer test, assert the exact heat gradient and selected marker paint:

```ts
const heat = addedLayers.find((layer) => layer.id === "civicpulse-incident-neutral-heat")
expect(heat?.paint["heatmap-opacity"]).toBe(0.68)
expect(heat?.paint["heatmap-color"]).toEqual([
  "interpolate", ["linear"], ["heatmap-density"],
  0, "rgba(0, 0, 0, 0)",
  0.15, "#2F80ED",
  0.38, "#22B8A7",
  0.6, "#F2C94C",
  0.8, "#F2994A",
  1, "#D64545",
])
const selected = addedLayers.find((layer) => layer.id === "civicpulse-incident-selected")
expect(selected?.paint).toMatchObject({
  "circle-color": "#ffffff",
  "circle-radius": 10,
  "circle-stroke-color": "#171a1c",
  "circle-stroke-width": 3,
})
```

Add a retry assertion:

```ts
renderer.retry()
expect(map.setStyle).toHaveBeenCalledWith(OPENFREEMAP_STYLE_URL)
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```powershell
pnpm vitest run src/features/incidents/adapters/map/maplibre-map-adapter.spec.ts
```

Expected: FAIL because the default is `FALLBACK_MAP_STYLE`, attribution is false, and existing heat/selection paints differ.

- [ ] **Step 3: Implement the online map and overlay paint**

In `maplibre-map-adapter.ts`, remove the `FALLBACK_MAP_STYLE` import and add:

```ts
export const OPENFREEMAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"

const DENSITY_COLOR_EXPRESSION = [
  "interpolate",
  ["linear"],
  ["heatmap-density"],
  0,
  "rgba(0, 0, 0, 0)",
  0.15,
  "#2F80ED",
  0.38,
  "#22B8A7",
  0.6,
  "#F2C94C",
  0.8,
  "#F2994A",
  1,
  "#D64545",
] as const
```

Change `MapFactoryOptions` to:

```ts
export interface MapFactoryOptions {
  readonly container: HTMLElement
  readonly style: unknown
  readonly center: readonly [number, number]
  readonly zoom: number
  readonly attributionControl: true
}
```

Replace `heatLayer` with a density-only gradient; category mode still filters features but does not change the meaning of colors:

```ts
function heatLayer(id: string, filter?: readonly unknown[]) {
  return {
    id,
    type: "heatmap" as const,
    ...(filter ? { filter } : {}),
    source: SOURCE_ID,
    paint: {
      "heatmap-weight": ["get", "intensity"],
      "heatmap-intensity": 1,
      "heatmap-radius": 24,
      "heatmap-opacity": 0.68,
      "heatmap-color": DENSITY_COLOR_EXPRESSION,
    },
  }
}
```

Use `heatLayer(NEUTRAL_LAYER_ID)` in All mode and `heatLayer(CATEGORY_LAYER_ID, filter)` in category mode. In `mount` and `retry`, resolve the style as:

```ts
const mapStyle = options.style ?? OPENFREEMAP_STYLE_URL
```

Pass `attributionControl: true`. Set the selected layer paint to:

```ts
paint: {
  "circle-color": "#ffffff",
  "circle-radius": 10,
  "circle-opacity": 0.98,
  "circle-stroke-color": "#171a1c",
  "circle-stroke-width": 3,
}
```

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```powershell
pnpm vitest run src/features/incidents/adapters/map/maplibre-map-adapter.spec.ts
```

Expected: all adapter tests pass, including lifecycle cleanup and retry.

- [ ] **Step 5: Commit Task 1**

```powershell
git add frontend/src/features/incidents/adapters/map/maplibre-map-adapter.ts frontend/src/features/incidents/adapters/map/maplibre-map-adapter.spec.ts
git commit -m "feat(map): use online street basemap and clear density palette"
```

---

### Task 2: Density legend and map control polish

**Files:**
- Modify: `frontend/src/features/incidents/ui/IncidentMapPanel.vue`
- Modify: `frontend/src/styles/base.css`
- Test: `frontend/src/features/incidents/ui/IncidentMapPanel.spec.ts`

**Interfaces:**
- Consumes: existing category filter and `IncidentMapRenderer` lifecycle API.
- Produces: one density legend with Low/High endpoints, styled retry control, readable map frame, and preserved degraded-state behavior.

- [ ] **Step 1: Write failing panel tests**

Replace category-color legend expectations with density semantics:

```ts
it("renders a density legend independent of category filtering", async () => {
  const renderer = rendererSpy("neutral-density")
  const wrapper = mount(IncidentMapPanel, {
    props: { incidents: [floodingIncident, drainIncident], createRenderer: () => renderer },
  })

  const legend = wrapper.get('[aria-label="Report density"]')
  expect(legend.text()).toContain("Low")
  expect(legend.text()).toContain("High")
  expect(legend.get("[data-density-gradient]").exists()).toBe(true)

  await wrapper.get("select").setValue("flooding")
  expect(wrapper.findAll('[aria-label="Report density"]')).toHaveLength(1)
})
```

Extend the degraded-state test:

```ts
const retry = wrapper.get("[data-map-retry]")
expect(retry.classes()).toContain("incident-map-panel__retry")
expect(retry.attributes("type")).toBe("button")
```

- [ ] **Step 2: Run the panel spec to verify RED**

Run:

```powershell
pnpm vitest run src/features/incidents/ui/IncidentMapPanel.spec.ts
```

Expected: FAIL because the panel still renders category swatches and the retry button has no variant class.

- [ ] **Step 3: Implement the density legend**

Remove `CATEGORY_COLORS`, `showNeutralFallback`, and the neutral/category color notice. Keep `CATEGORY_OPTIONS` for filtering. Add this inside `.incident-map-panel__map-wrap`, after the map container:

```vue
<div
  class="incident-map-panel__density-legend"
  aria-label="Report density"
>
  <span>Low</span>
  <span
    class="incident-map-panel__density-gradient"
    data-density-gradient
    aria-hidden="true"
  />
  <span>High</span>
</div>
```

Add `class="incident-map-panel__retry"` to the existing retry button. Do not change lifecycle text or event handling.

- [ ] **Step 4: Style the map frame and legend in `base.css`**

Use the existing `.incident-map-panel*` section and add:

```css
.incident-map-panel__map-wrap {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--divider);
  background: #dfe8ea;
}

.incident-map-panel__density-legend {
  position: absolute;
  right: var(--space-3);
  bottom: calc(var(--space-3) + 1.5rem);
  z-index: 2;
  display: grid;
  grid-template-columns: auto minmax(7rem, 10rem) auto;
  align-items: center;
  gap: var(--space-2);
  padding: 0.45rem 0.6rem;
  border: 1px solid rgb(23 26 28 / 18%);
  background: rgb(255 255 255 / 92%);
  box-shadow: 0 4px 16px rgb(23 26 28 / 12%);
  color: var(--graphite);
  font-size: var(--text-small);
  font-weight: 700;
}

.incident-map-panel__density-gradient {
  height: 0.55rem;
  background: linear-gradient(90deg, #2F80ED, #22B8A7, #F2C94C, #F2994A, #D64545);
}

.incident-map-panel__retry {
  min-height: 2.75rem;
  padding: 0.55rem 0.85rem;
  border: 1px solid var(--civic-blue);
  background: var(--paper-white);
  color: var(--civic-blue);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.incident-map-panel__retry:focus-visible {
  outline: 2px solid var(--paper-white);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px var(--civic-blue);
}
```

At narrow widths, keep the legend inside the map and above attribution:

```css
@media (max-width: 40rem) {
  .incident-map-panel__density-legend {
    right: var(--space-2);
    bottom: 2rem;
    grid-template-columns: auto minmax(5rem, 1fr) auto;
    max-width: calc(100% - 2 * var(--space-2));
  }
}
```

- [ ] **Step 5: Run map UI tests and frontend lint**

Run:

```powershell
pnpm vitest run src/features/incidents/ui/IncidentMapPanel.spec.ts src/features/incidents/adapters/map/maplibre-map-adapter.spec.ts
pnpm run lint
```

Expected: all focused tests pass and ESLint reports zero warnings.

- [ ] **Step 6: Commit Task 2**

```powershell
git add frontend/src/features/incidents/ui/IncidentMapPanel.vue frontend/src/features/incidents/ui/IncidentMapPanel.spec.ts frontend/src/styles/base.css
git commit -m "feat(map): add readable density legend and map controls"
```

---

### Task 3: Polished semantic photo and form buttons

**Files:**
- Modify: `frontend/src/features/submissions/ui/SubmitPage.vue`
- Test: `frontend/src/features/submissions/ui/SubmitPage.spec.ts`

**Interfaces:**
- Consumes: existing file input, `retryUpload`, `clearPhoto`, submission retry/reset, and upload state.
- Produces: accessible custom file-button presentation plus primary, secondary, and quiet-danger button variants.

- [ ] **Step 1: Write failing semantic/class tests**

Add a default-state test:

```ts
it("presents the native photo input through a styled accessible upload control", () => {
  const wrapper = mountPage()
  const input = wrapper.get('input[type="file"]')
  const label = wrapper.get('label[for="report-photo"]')

  expect(input.classes()).toContain("submit-page__file-input")
  expect(label.classes()).toContain("submit-page__file-button")
  expect(label.text()).toContain("Upload photo")
})
```

Extend failed-upload and submit-state tests:

```ts
expect(wrapper.get("[data-retry-upload]").classes()).toContain("submit-page__button--secondary")
expect(wrapper.get("[data-remove-photo]").classes()).toContain("submit-page__button--danger")
expect(wrapper.get('button[type="submit"]').classes()).toContain("submit-page__button--primary")
```

Keep existing file-selection helpers pointed at `#report-photo`; hiding it visually must not change tests or behavior.

- [ ] **Step 2: Run the SubmitPage spec to verify RED**

Run:

```powershell
pnpm vitest run src/features/submissions/ui/SubmitPage.spec.ts
```

Expected: FAIL because the upload label and button variant classes do not exist.

- [ ] **Step 3: Implement semantic control markup**

Replace the visible photo label/input block with:

```vue
<span class="submit-page__photo-label">
  Photo evidence <span class="submit-page__optional">(optional)</span>
</span>
<input
  id="report-photo"
  ref="fileInput"
  class="submit-page__file-input"
  type="file"
  accept="image/jpeg,image/png"
  @change="onPhotoChange"
>
<label
  for="report-photo"
  class="submit-page__file-button submit-page__button submit-page__button--secondary"
>
  <span aria-hidden="true">↑</span>
  <span>{{ selectedFile === null ? "Upload photo" : "Choose another photo" }}</span>
</label>
```

Apply these exact classes/data hooks:

```vue
<button
  v-if="photoUpload.kind === 'failed'"
  type="button"
  class="submit-page__button submit-page__button--secondary"
  data-retry-upload
  @click="retryUpload"
>
  Retry upload
</button>
<button
  type="button"
  class="submit-page__button submit-page__button--danger"
  data-remove-photo
  @click="clearPhoto"
>
  Remove photo
</button>
```

Use `submit-page__button--primary` on the form submit button and `submit-page__button--secondary` on submission retry and “Submit another report”. Preserve all existing labels and disabled expressions.

- [ ] **Step 4: Implement scoped button CSS**

Replace the raw file-input and generic button rules with:

```css
.submit-page__file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  white-space: nowrap;
}

.submit-page__button,
.submit-page__file-button {
  display: inline-flex;
  min-height: 2.75rem;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: fit-content;
  padding: 0.55rem 0.9rem;
  border: 1px solid transparent;
  border-radius: 4px;
  font: inherit;
  font-weight: 700;
  line-height: 1.2;
  cursor: pointer;
  transition: transform 120ms ease, background-color 120ms ease, border-color 120ms ease;
}

.submit-page__button--primary {
  border-color: var(--civic-blue);
  background: var(--civic-blue);
  color: var(--paper-white);
}

.submit-page__button--secondary,
.submit-page__file-button {
  border-color: var(--civic-blue);
  background: color-mix(in srgb, var(--civic-blue) 7%, var(--paper-white));
  color: var(--civic-blue);
}

.submit-page__button--danger {
  border-color: color-mix(in srgb, var(--critical) 55%, var(--divider));
  background: var(--paper-white);
  color: var(--critical);
}

.submit-page__button:hover:not(:disabled),
.submit-page__file-button:hover {
  transform: translateY(-1px);
}

.submit-page__button:focus-visible,
.submit-page__file-input:focus-visible + .submit-page__file-button {
  outline: 2px solid var(--paper-white);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px var(--civic-blue);
}

.submit-page__button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

@media (prefers-reduced-motion: reduce) {
  .submit-page__button,
  .submit-page__file-button {
    transition: none;
  }
}
```

Use the repository's actual critical-color token name from `styles/tokens.css`; if it is not `--critical`, add no token and use the existing critical hex value already used by the app.

- [ ] **Step 5: Run focused and full frontend verification**

Run:

```powershell
pnpm vitest run src/features/submissions/ui/SubmitPage.spec.ts
pnpm run check
git diff --check
```

Expected: focused tests pass; API check, ESLint, all Vitest tests, typecheck, and build pass; diff check has no whitespace errors.

- [ ] **Step 6: Live browser verification**

Start the existing local API and frontend, then use Playwright CLI to verify:

1. The incident map shows OpenFreeMap roads and place labels.
2. The density gradient remains readable while street labels are visible.
3. The Report density legend stays clear of map attribution at desktop and 390 px viewport width.
4. Selecting a queue incident produces the white marker with dark outline.
5. The Upload photo label opens the native file chooser and remains keyboard focusable.
6. Retry upload, Remove photo, disabled submit, and primary submit states use the intended variants and have visible focus.
7. Browser console contains no new map-style, CORS, or accessibility errors.

- [ ] **Step 7: Commit Task 3**

```powershell
git add frontend/src/features/submissions/ui/SubmitPage.vue frontend/src/features/submissions/ui/SubmitPage.spec.ts
git commit -m "feat(frontend): polish photo and submission controls"
```

---

## Final Verification

After all three task reviews:

```powershell
cd frontend
pnpm run check
cd ..
uv run --offline python -m pytest -q
uv run --offline pyright src scripts
git diff --check
git status --short
```

Expected: all frontend and backend gates pass and the worktree contains no uncommitted tracked changes.
