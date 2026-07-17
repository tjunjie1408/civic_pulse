# CivicPulse Vue Slice 3 Map Selection and Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each behavior. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing MapLibre density spike with synchronized queue/map selection, metre-accurate affected-radius overlays, and a recoverable base-map lifecycle without losing incident data.

**Architecture:** Keep geodesic projection pure in `domain/`, keep MapLibre sources, layers, events, and lifecycle state inside the map adapter, and let `IncidentQueuePage` own committed and preview selection. The queue row and map panel communicate through typed Vue props and emits; neither reconstructs API ordering or operational policy.

**Tech Stack:** Vue 3 Composition API, strict TypeScript, MapLibre GL JS, Vitest, Vue Test Utils, and the existing typed map renderer port.

## Global Constraints

- Preserve API-owned incident order byte-for-byte and never derive a numeric priority score.
- Keep category hue, density intensity, operational priority, and affected radius as independent visual facts.
- Do not include pending review evidence in confirmed heat or draw review evidence as a confirmed affected-area boundary.
- Do not create a second MapLibre instance during degraded/recovery; teardown removes all listeners, layers, and sources exactly once.
- A map failure preserves the last incident data, selection, overlays, legend, and queue access.
- Use `radius_metres` as a geodesic polygon or equivalent metre-accurate overlay; heatmap pixel radius is not the reported affected distance.
- Preserve unrelated working-tree changes, including `CLAUDE.md`, the July 17 rebuild plan, and the existing default proxy behavior.

---

### Task 1: Add pure radius projection and typed map view contracts

**Files:**
- Create: `frontend/src/features/incidents/domain/radius-overlay.ts`
- Create: `frontend/src/features/incidents/domain/radius-overlay.spec.ts`
- Modify: `frontend/src/features/incidents/application/incident-map-port.ts`

- [x] Write failing tests for a 0-metre center point, a positive-radius closed polygon, metre-scale north/east offsets, and exclusion of non-finite coordinates.
- [x] Define `IncidentMapView` with `incidents`, `cells`, `mode`, `selectedIncidentId`, and `hoveredIncidentId`.
- [x] Define `MapLifecycleState` as `loading | ready | degraded | recovering` and typed callbacks for incident selection, preview, and lifecycle updates.
- [x] Implement a fixed-segment geodesic destination calculation using the WGS84 mean Earth radius, preserving longitude/latitude GeoJSON order and returning a closed polygon.
- [x] Keep radius projection independent of MapLibre and operational priority policy.
- [x] Run the focused domain tests, typecheck, and lint.

### Task 2: Extend the MapLibre adapter with overlays and lifecycle recovery

**Files:**
- Modify: `frontend/src/features/incidents/adapters/map/maplibre-map-adapter.ts`
- Modify: `frontend/src/features/incidents/adapters/map/maplibre-map-adapter.spec.ts`

- [x] Add failing adapter tests for radius and centroid sources, selected-feature styling, click-to-select, degraded state on map error, recovery through `setStyle`, re-render after `style.load`, and no duplicate resources/listeners after recovery or dispose.
- [x] Render the existing deterministic heat source/layer plus a separate GeoJSON affected-area source and centroid source; never use heatmap radius as the reported radius.
- [x] Store the last complete `IncidentMapView` and reapply it after style recovery without creating a second map.
- [x] Emit `degraded` on provider/style errors, `recovering` on bounded retry, and `ready` only after the recovered style is loaded.
- [x] Register one typed incident-point click listener and expose unsubscribe functions through the application port.
- [x] Keep the neutral fallback visible when the base map is unavailable and preserve overlays and selection metadata.
- [x] Run focused adapter tests, frontend tests, typecheck, and lint.

### Task 3: Synchronize queue-row and map selection

**Files:**
- Modify: `frontend/src/features/incidents/ui/IncidentQueueRow.vue`
- Modify: `frontend/src/features/incidents/ui/IncidentQueueRow.spec.ts`
- Modify: `frontend/src/features/incidents/ui/IncidentMapPanel.vue`
- Modify: `frontend/src/features/incidents/ui/IncidentMapPanel.spec.ts`
- Modify: `frontend/src/features/incidents/ui/IncidentQueuePage.vue`
- Modify: `frontend/src/features/incidents/ui/IncidentQueuePage.spec.ts`

- [x] Write failing component tests for row selection, keyboard activation, hover/focus preview, map selection emitting the matching incident ID, selected/hovered state attributes, and one committed selection shared by both surfaces.
- [x] Make each row a semantic keyboard-operable selection control without changing its existing evidence facts or API order.
- [x] Let the page own `selectedIncidentId` and `hoveredIncidentId`; pass them into both children and clear preview state without changing committed selection.
- [x] Scroll the selected row into view only when selection changes from the map or keyboard; do not sort or recreate the incident list.
- [x] Pass the complete `IncidentMapView` to the renderer and expose map lifecycle status as a specific accessible status message while retaining queue data.
- [x] Run focused component tests, the full Vitest suite, typecheck, and lint.

### Task 4: Verify the slice and document the temporary proxy override

**Files:**
- Modify: `README.md`
- Modify: `frontend/src/App.spec.ts` only if the new map lifecycle status changes the shell contract.

- [x] Document `CIVICPULSE_API_PROXY_TARGET` as a temporary local override whose default remains `http://127.0.0.1:8000`.
- [x] Run `pnpm --dir frontend run check` and targeted backend contracts.
- [x] Start the API and Vite on free temporary ports without touching port 8000, then verify desktop and 1024px rendered states, map selection, degraded status, no horizontal overflow, and console health.
- [x] Run `git diff --check` and confirm only intentional implementation/documentation files are changed; preserve unrelated untracked files.
