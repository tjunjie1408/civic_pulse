# CivicPulse Vue Photo Map Design

Date: 2026-07-16
Status: Approved visual and architecture direction

## 1. Problem

The current Streamlit dashboard is functional but difficult to understand on first entry. The
map uses generic points, incident detail exposes identifiers instead of operational context, and
complaints cannot upload or display field photos. The redesign must make location, severity,
affected area, evidence, and next action understandable without requiring prior knowledge of the
matching and clustering model.

The new interface serves a municipal operations officer. Its primary job is to answer, in order:

1. Where are active incidents?
2. What type of incident is each area showing?
3. How severe is it and how far does its confirmed impact extend?
4. Which incident needs attention first?
5. What reports and field photos support that incident?

## 2. Scope and Priorities

### Normative language

This document uses three requirement strengths:

- **MUST** identifies domain invariants, security boundaries, dependency direction, and visual
  semantics that an implementation cannot reinterpret.
- **SHOULD** identifies the preferred module organization, component boundaries, and test
  layering. A deviation requires a written reason and equivalent verification.
- **MAY** identifies replaceable implementation choices such as a client-state library, query
  library, virtual-list library, or exact internal directory structure.

The requirement strength applies to the behavior, not to incidental examples or pseudocode.

### P0

- Add a Vue 3 and TypeScript frontend while retaining the existing Streamlit dashboard until
  feature parity is verified.
- Replace the current prototype map with a MapLibre GL JS map.
- Verify deterministic category-aware incident heat and render either that exact result or the
  declared neutral fallback, together with accurate affected-area overlays.
- Preserve map, incident, and evidence access through the base-map fallback lifecycle.
- Synchronize map selection with a scrollable incident accordion.
- Accept one JPEG or PNG photo per complaint and display incident-level photo collections.
- Keep the existing FastAPI service, matching, clustering, priority, review, and SQLite layers.
- Preserve API-owned incident ordering and many-to-many snapshot transitions.
- Keep pending review in a separate review view and map mode.

### P1

- Refine keyboard navigation, responsive layouts, and loading states.
- Add visual regression coverage and performance budgets for the Vue application.

### P3

- Optional terrain, building extrusion, or 3D incident presentation.

### Non-goals

- Photo authenticity, capture-time, or reported-location verification.
- AI photo analysis in the first release.
- Using photos to alter matching, clustering, priority, or automatic rejection.
- Replacing the FastAPI service or civic incident domain model.
- Removing Streamlit before the Vue frontend passes its parity gate.

## 3. Governing Invariants

- **MUST:** only `AUTO_MATCH` confirmed evidence forms incident membership and operational
  priority.
- **MUST:** pending review candidates remain visually and semantically separate from confirmed
  incidents.
- **MUST:** incident IDs remain membership-derived snapshot identifiers, not permanent case IDs.
- **MUST:** a photo upload failure cannot roll back or hide a successfully submitted text
  complaint.
- **MUST:** a photo never changes incident matching, priority, or authenticity claims.
- **MUST:** the browser never supplies or receives an arbitrary server filesystem path.
- **MUST:** map category, operational priority, density, and affected area encode different facts
  and must not be conflated.
- **MUST:** the frontend preserves API ordering and transition metadata; it does not reconstruct
  domain policy from display data.

## 4. Frontend Architecture

The Vue application is a separate HTTP client of the existing FastAPI API.

```text
Vue 3 + TypeScript + Vite
    -> typed API client
    -> FastAPI /api/v1
        -> CivicPulseService
        -> matching, clustering, priority, review
        -> SQLite repository

MapLibre GL JS
    -> configurable vector base-map style
    -> category heat layers
    -> affected-radius GeoJSON overlays

Streamlit dashboard
    -> remains available during migration
    -> is removed only after explicit parity approval
```

Vue uses Composition API and `<script setup lang="ts">`. MapLibre is integrated directly rather
than through a Vue wrapper so its lifecycle, events, and style layers remain explicit and typed.
The first release uses MapLibre native layers. deck.gl is deferred until measured data volume or
animation requirements justify the additional renderer.

The base-map style URL is configuration, not a request field or embedded secret. A tile failure
does not remove incident data: the interface falls back to a neutral coordinate canvas and keeps
incident overlays, the event index, and evidence accessible. Provider attribution remains visible.

The frontend's project-level `AGENTS.md` **MUST** contain only stable boundaries: domain
invariants, API ownership, dependency direction, security rules, and required verification. It
**MUST NOT** prematurely require Pinia, TanStack Query, a virtual-list package, or another
replaceable implementation choice. An architecture skill **SHOULD** guide implementation and
review workflow without duplicating or redefining CivicPulse domain policy. TypeScript, ESLint,
dependency-boundary checks, and tests **MUST** enforce the mechanically checkable rules.

Feature views and UI components **MUST** depend on typed application/API boundaries rather than
repository, storage, or generated transport internals. The exact state library, query library,
virtualization library, and internal folder details remain **MAY** choices until a vertical slice
demonstrates the need.

## 5. Map Semantics

### Independent visual facts

The map **MUST** keep these channels independent:

| Visual channel | Meaning | Source |
| --- | --- | --- |
| Hue | Incident category | confirmed incident category |
| Depth within the hue | Operational priority band | confirmed `priority.level` |
| Heat intensity | Spatial concentration | deterministic density calculation |
| Geographic area | Reported affected radius | `radius_metres` |

Category hues are restricted to the map, its legend, and the corresponding event-type label:

| Category | API value | Base hue |
| --- | --- | --- |
| Flooding | `flooding` | `#246B9E` |
| Blocked drain | `blocked_drain` | `#3C7F84` |
| Pothole / road | `pothole` | `#A9792D` |
| Rubbish | `rubbish` | `#99566A` |
| Street light | `street_light` | `#6D6792` |
| Other | `other` | `#747C82` |

The operational bands `critical`, `high`, `medium`, and `low` **MUST** each have a fixed,
documented depth stop within the same category hue. A confirmed incident whose priority is `null`
because its evidence conflicts **MUST** use a neutral, text-labelled `No operational priority`
state. It **MUST NOT** be mapped to `low` or included in category heat aggregation. The priority
band is categorical domain data; the frontend **MUST NOT** invent or expose a numeric priority
score. Density intensity is a rendering value only and **MUST NOT** be reused for operational
ordering.

### Deterministic multi-category density

`All` mode **MUST** permit multiple incident categories to appear at the same time, while each
density-grid cell displays exactly one category hue. Additive blending, RGB mixing, and renderer-
dependent alpha compositing between category heat layers are prohibited.

For every cell, the grid calculation compares the heat intensity contributed by each eligible
category and assigns the category with the greatest intensity as `dominantCategory`. Exact ties
**MUST** use this frozen order:

```text
flooding
blocked_drain
pothole
rubbish
street_light
other
```

Each eligible confirmed complaint contributes to exactly its API-assigned category at its
reported coordinate. The grid **MUST NOT** treat `category_summary[0]` as a primary or dominant
category: the current API defines `category_summary` as a set-like summary, not a ranking. Kernel,
bandwidth, weighting, cell size, and time-window parameters **MUST** be explicit and versioned so
identical eligible inputs produce identical cells.

The result **MUST NOT** change because of API response order, JavaScript object iteration order,
MapLibre layer order, or the number of incidents currently inside the viewport. Inputs are the
complete confirmed incident result set for the active time and category filters, not merely the
currently visible or paginated rows. Pending review evidence and confirmed conflict incidents with
`priority: null` do not contribute to this grid.

P0 **SHOULD** produce one deterministic density grid before rendering. The grid may be produced
by the API or by a pure typed client module after data-volume measurement; this design does not
preselect that deployment boundary. Its renderer-facing contract is conceptually:

```ts
interface HeatCell {
  longitude: number
  latitude: number
  intensity: number
  dominantCategory: IncidentCategory
}
```

The grid is generated for the active filter mode. `All` computes dominance across all eligible
categories. A single-category mode computes and renders only the selected category, so cells that
were dominated by another category in `All` are not incorrectly discarded.

Before committing the renderer, the first map vertical slice **MUST** include a measured spike
that verifies whether MapLibre native layers can render this grid with stable single-hue cells,
correct zoom behavior, and no unintended cross-layer blending. Acceptable P0 outcomes are:

1. render the unified dominant-category grid with native layers; or
2. if that cannot be made stable within the P0 performance and complexity budget, explicitly
   render a neutral total-density heatmap with category detail available through filters, labels,
   and incident selection.

A fixed category layer stack is not an exact implementation of dominance. It may be evaluated
only as a documented approximation during the spike and **MUST NOT** ship if it produces dirty
colors or order-dependent results. The implementation must use the neutral total-density fallback
rather than silently blend category hues.

### Area and zoom behavior

`radius_metres` **MUST** be rendered as a geodesic polygon or equivalent metre-accurate overlay.
A MapLibre heatmap pixel radius is not presented as a real-world affected distance. At district
zoom, the density grid communicates concentration. At close zoom, the interface transitions to
the incident boundary, centroid, and confirmed complaint points.

Color is never the only carrier of meaning. Labels and event rows state category, priority, report
count, and radius in text. All color and intensity domains remain stable across zoom and viewport
changes.

## 6. Visual System

The government interface uses a white, neutral shell. Color is scarce and semantic.

### Neutral tokens

- Canvas: `#F7F8F9`
- Surface: `#FFFFFF`
- Primary text: `#171A1C`
- Secondary text: `#70787E`
- Divider: `#E3E7E9`
- Base map land: `#E8ECEE`
- Base map water: `#D2DDE2`
- Critical text only: `#A53E3E`

The UI uses Geist Sans when self-hosted assets are available, then Aptos, Noto Sans, and the system
sans-serif stack. Body copy prioritizes readability over narrow or display typography. Data uses
tabular numerals; monospace is limited to compact identifiers and coordinates.

The interface avoids large colored surfaces, decorative gradients, glass effects, heavy shadows,
pill-heavy layouts, and card containers around every value. Dividers, whitespace, typography, and
alignment establish hierarchy. Heat gradients are allowed only inside the map because they encode
measured spatial density.

## 7. Layout and Interaction

Desktop uses a map-first split:

```text
+------------------------------------------------+-----------------------+
|                                                | Active incidents      |
|                                                |                       |
|             Map, approximately 72%             | Event A, collapsed    |
|                                                | Event B, expanded     |
|                                                |   description         |
|                                                |   facts and radius    |
|                                                |   complaint photos    |
|                                                | Event C, collapsed    |
+------------------------------------------------+-----------------------+
```

The incident index is scrollable and permits exactly one expanded incident. An expanded event
contains its description, priority, confirmed report count, affected radius, latest update, a
bounded preview of confirmed reports, a bounded set of photo thumbnails, and an
`Open full incident` action. Preview contracts **MUST** include total counts and an explicit
`has_more` or equivalent signal; the accordion **MUST NOT** grow into an unbounded incident-detail
page. Exact preview limits are an API contract and **MAY** be tuned without changing the domain
model. Photos are never rendered as an unrelated panel below the event list.

Full evidence and history live at `/incidents/:snapshotId`. If that snapshot is stale when opened
or becomes stale while loaded, P0 **MUST** return the user to the incident queue and show a clear
notice that incident membership changed. It **MUST NOT** guess which successor represents the
user's intent after a split or merge. The notice may offer explicit links when the API supplies
current snapshot IDs.

Selection is synchronized:

- Clicking a map incident opens and scrolls the corresponding event into view.
- Clicking an event focuses and emphasizes the corresponding map area.
- Hovering or focusing an event previews its map area without changing the committed selection.
- Selecting a new event closes the previous event.
- Clicking a thumbnail opens a keyboard-accessible photo viewer.
- Escape closes the viewer and focus returns to the invoking thumbnail.

Pending review is a separate review view, not an accordion state inside the confirmed incident
queue. Its map representation **MUST** use neutral evidence locations and review relationships
only. It **MUST NOT** draw a heat region, affected-radius boundary, or other shape that implies a
confirmed incident footprint.

On narrow screens, the map appears first and the event index follows as a single column. Selection
state persists while the layout changes.

## 8. Photo Upload and Storage

The MVP supports one photo per complaint. Multiple complaints inside one incident naturally form
an incident photo collection.

The API owns file storage through a two-step flow:

1. The client uploads one file to a dedicated multipart photo endpoint.
2. The server validates and sanitizes the file, then returns an opaque `photo_id`.
3. Complaint submission references `photo_id`, never `photo_path`.
4. Complaint and incident responses expose a safe API photo URL or typed photo reference.

The photo step is optional. If upload validation or transport fails, the client preserves the
complaint draft and offers both retry and "submit without photo" actions. A failed upload never
blocks a valid text complaint.

Upload rules:

- Maximum uploaded file size: 5 MiB, enforced while streaming rather than after buffering the
  entire request.
- Accepted decoded formats: JPEG and PNG only.
- Declared MIME type and filename are not trusted.
- Pillow must decode and verify the image.
- The server re-encodes accepted images to remove metadata and embedded payloads.
- The server generates the storage filename from a UUID.
- Writes use a temporary file followed by an atomic rename.
- Failed validation leaves no file behind.
- Unreferenced uploads expire and are cleaned up by a bounded maintenance operation.
- API errors do not expose absolute paths, provider details, or sensitive metadata.

The current `photo_path` field may remain an internal migration detail, but it is removed from
client-writable contracts. Seed data continues to support missing photos.

## 9. API Contract Changes

The Vue frontend requires typed contracts for:

- Photo upload response with `photo_id`, sanitized content type, byte size, and safe read URL.
- Complaint create request using optional `photo_id` instead of client-supplied `photo_path`.
- Complaint response containing an optional photo reference.
- Incident detail containing confirmed complaint summaries, not only complaint IDs, so the event
  accordion can display descriptions, report times, locations, and photo references.
- Bounded incident previews with total counts and a `has_more` equivalent.
- Snapshot transition metadata containing collections of previous and current snapshot IDs.
- Density-grid data or the complete eligible inputs required to reproduce it deterministically.

The incident queue order is owned by the API and is frozen as:

1. `priority` rank (`critical`, `high`, `medium`, `low`, followed by no operational priority);
2. `latest_reported_at` descending; and
3. `incident_id` ascending as the stable final tie-breaker.

The frontend **MUST** preserve this order. It does not recompute priority, sort by a locally
invented score, or allow map rendering order to change the operational queue. User-selected
filters may reduce the returned set, but they do not redefine the order within it.

OpenAPI remains the source of truth. The frontend client types are generated or mechanically
validated from the frozen schema. The server keeps strict request and response models. TypeScript
types alone do not validate runtime response data; if the implementation requires runtime rejection,
it **SHOULD** generate or mechanically synchronize that validation rather than hand-maintain a
second schema.

## 10. State and Failure Handling

Frontend state distinguishes:

- remote server state;
- selected incident snapshot ID;
- hovered incident snapshot ID;
- active category filters;
- open photo ID;
- upload progress and retry eligibility.

The selected snapshot must follow API-provided transition metadata after complaint submission or
review resolution. Transition metadata **MUST** retain multiple `previous_snapshot_ids` and
multiple `current_snapshot_ids`; the API and frontend **MUST NOT** collapse a split or merge into a
single `previous/current` pair. A one-to-one transition may update a local selection. A split,
merge, missing successor, or stale detail route returns to the queue with an explanation and lets
the officer choose explicitly.

### Base-map lifecycle contract

The map owns an explicit lifecycle independent of incident server state:

1. `loading`: initialize the renderer and base-map style while retaining the incident-list
   loading state separately;
2. `ready`: base map and CivicPulse sources/layers are available;
3. `degraded`: a style, tile, or provider failure replaces the base map with the neutral canvas
   while preserving incident selection, overlays, legend, event index, and evidence access;
4. `recovering`: a bounded retry or later style success restores the configured base map and
   reattaches CivicPulse sources, layers, event handlers, and selection exactly once.

Entering `degraded` **MUST NOT** clear valid incident data or create a second map instance. Style
reloads and recovery **MUST NOT** duplicate sources, layers, listeners, camera actions, or
selection events. The implementation **SHOULD** isolate this lifecycle behind a typed map adapter
so component teardown always removes listeners and renderer resources. A particular retry helper
or state library remains a **MAY** choice.

Required failure states:

- Base map unavailable: keep neutral map canvas and all incident overlays.
- Incident list unavailable: show a specific retry action without clearing the last valid map.
- Photo unavailable: preserve complaint text and display an evidence-unavailable message.
- Upload rejected: explain format or size limits and allow a replacement file.
- Complaint succeeds after photo failure: report the complaint as saved and the photo as omitted.
- Snapshot replaced: follow only an unambiguous one-to-one transition; otherwise return to the
  queue and present all API-provided current snapshot IDs.

## 11. Motion and Accessibility

Motion communicates selection and state change only:

- affected-radius outline expands when an incident becomes selected;
- non-selected map areas reduce emphasis;
- the matching event accordion opens;
- the map camera focuses without disorienting jumps;
- the photo viewer uses a short opacity and transform transition.

All motion respects `prefers-reduced-motion`. Keyboard focus is visible. Map selection has an
equivalent event-list control. Text and controls meet WCAG AA contrast. Photos include functional
alternative text when available; otherwise the complaint description supplies context outside the
image.

## 12. Verification Plan

### Backend

- Unit tests for valid JPEG and PNG uploads.
- Negative tests for empty, malformed, renamed, unsupported, oversized, and traversal-like input.
- Tests proving metadata removal, UUID filenames, atomic writes, and cleanup after failure.
- Integration tests for upload, complaint reference, idempotent replay, restart persistence, and
  safe photo retrieval.
- Tests proving a photo failure cannot alter incident membership or priority.

### Frontend

- Unit tests for category hue, all four priority depths, neutral conflict state, and radius
  projection.
- Determinism tests that shuffle API input and object insertion order and vary the viewport while
  asserting identical `dominantCategory` cells.
- Tie tests covering every adjacent pair in the frozen dominant-category order.
- Tests proving single-category mode is computed independently and pending review or
  `priority: null` conflict incidents never enter heat aggregation.
- Unit tests for one-open-event accordion, bounded previews, and many-to-many snapshot transition
  state.
- Component tests for map-to-event and event-to-map synchronization.
- Contract tests proving the incident index preserves API order and never derives a numeric
  priority score.
- Lifecycle tests for ready, degraded, recovery, style reload, and teardown without duplicate
  MapLibre resources or events.
- Accessibility tests for accordion controls, focus return, photo viewer, and keyboard operation.
- Responsive and visual regression checks at desktop, tablet, and mobile sizes.

### End to end

1. Upload a valid photo.
2. Submit a complaint with an idempotency key.
3. Observe the current incident snapshot on the map.
4. Select the map area and verify the matching event expands.
5. Open the photo and verify it is served through the API.
6. Repeat the same submission and verify no duplicate complaint or photo association is created.
7. Resolve a review and follow one-to-one API transition metadata.
8. Exercise a split and a merge and verify all previous/current snapshot IDs remain visible.
9. Open a stale incident URL and verify the UI returns to the queue with a clear notice.
10. Simulate a tile/style failure and recovery without losing incident selection or duplicating
    overlays.

The full Python suite, Pyright, Ruff, OpenAPI contract check, hybrid matching benchmark, Vue type
check, frontend unit tests, and browser end-to-end tests form the release gate.

### Capability parity gate

Streamlit remains available until an explicit checklist confirms that the Vue frontend can:

- load the API-owned incident queue in the same operational order;
- distinguish confirmed incidents, pending review evidence, and no-priority conflict incidents;
- filter incident categories without changing their semantic meaning;
- select from either the map or queue and preserve synchronized selection;
- inspect bounded evidence previews and open full incident detail;
- upload an optional photo, submit without one after failure, and safely retrieve evidence;
- approve and reject reviews, reconfirm stale review evidence, and never treat candidates as
  confirmed membership before resolution;
- follow one-to-one snapshot updates and present split, merge, or stale transitions safely;
- perform the current safe demo-reset workflow with equivalent confirmation and recovery behavior;
- remain operational when the base-map provider fails; and
- expose loading, empty, error, retry, keyboard, and narrow-screen states for each critical
  workflow.

Parity means workflow and domain-capability parity, not pixel parity with Streamlit. Retirement
requires this checklist, the release gate, and explicit product approval.

### Implementation slices

Implementation **SHOULD** proceed as independently runnable, testable, and reversible vertical
slices. Each slice includes its API contract, typed client boundary, smallest complete UI, tests,
and rollback point:

1. establish the Vue shell, generated/validated API types, and API-ordered incident queue;
2. spike MapLibre native rendering with the deterministic density grid and choose either exact
   dominant-category rendering or the declared neutral fallback;
3. deliver synchronized map selection, affected-radius overlays, and the degraded-map lifecycle;
4. deliver the bounded accordion and `/incidents/:snapshotId` detail route, including stale and
   many-to-many transition behavior;
5. deliver pending review as a separate view and neutral evidence map;
6. deliver secure photo upload, complaint attachment, retrieval, and viewer; and
7. close accessibility, responsive, performance, visual regression, and capability-parity gates.

No slice may silently redefine matching, priority, review, or snapshot semantics to simplify its
UI. A replaceable library choice is made only when the slice provides evidence that it is needed.

## 13. Risks and Mitigations

- **Misleading map area:** render `radius_metres` separately from pixel heat radius and label both.
- **Color ambiguity:** add category and priority text, maintain fixed legend semantics, and render
  one deterministic dominant category per density cell.
- **Renderer-dependent blending:** verify native MapLibre behavior in the first map slice and use
  the declared neutral total-density fallback if exact dominance is not stable.
- **Implicit queue policy:** consume API ordering directly and prohibit frontend-derived priority
  scores or re-ranking.
- **False confirmation:** keep review evidence out of incident heat and avoid boundaries that imply
  unconfirmed affected areas.
- **Orphaned uploads:** expire unreferenced photo IDs and clean bounded batches.
- **Tile-provider outage or licensing:** use a configurable provider, preserve attribution, and keep
  a neutral incident-overlay fallback.
- **Migration divergence:** keep one OpenAPI contract and retire Streamlit only after parity.
- **Photo storage growth:** enforce one photo per complaint, 5 MiB input limit, re-encoding, and
  documented cleanup.
- **UI overload with many incidents:** use a virtualizable scrollable index with one expanded row.
- **Snapshot ambiguity:** preserve multi-ID transitions and return stale, split, or merged detail
  views to the queue for explicit user choice.

## 14. Acceptance Criteria

The design is ready for implementation planning when all of the following are accepted:

- Vue and Streamlit coexist during migration.
- The MapLibre P0 spike proves exact dominant-category rendering or activates the explicit neutral
  total-density fallback.
- The white government visual system is the application shell.
- Category hue, density intensity, four-band priority depth, and affected radius have distinct
  semantics.
- `All` mode uses deterministic dominant-category cells with the frozen tie-break order and no
  additive or RGB blending.
- Pending review and no-priority conflict incidents do not contribute to confirmed heat.
- The frontend preserves API ordering and never invents a numeric priority score.
- Accordion rows contain bounded evidence previews; full evidence lives at
  `/incidents/:snapshotId`.
- Snapshot transitions preserve multiple previous and current IDs, and stale detail routes return
  safely to the queue.
- The base-map fallback lifecycle preserves overlays, selection, evidence access, and clean
  recovery.
- One safe photo per complaint is the MVP upload contract.
- Capability parity is verified by workflow before Streamlit retirement.
- Delivery is organized as reversible vertical slices.
- AI photo analysis and 3D presentation remain outside P0.
