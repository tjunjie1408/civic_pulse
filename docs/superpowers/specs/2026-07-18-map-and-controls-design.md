# CivicPulse Online Street Map and Control Polish Design

## Goal

Improve operational map readability and remove raw browser-control styling without changing CivicPulse's incident semantics or information architecture. The map must show recognizable streets and place labels, while overlays remain legible. Submission controls must feel consistent with the existing CivicPulse visual system.

## Scope

This change covers:

- the incident queue MapLibre basemap and overlay presentation;
- a compact heat-intensity legend and distinct selected-incident state;
- shared styling for file upload, retry, remove, and related form action buttons;
- focused unit/component tests and live browser verification.

It does not change matching, clustering, priority, incident ordering, API contracts, or photo storage behavior.

## Map Direction

Use the public OpenFreeMap MapLibre style as the online basemap. It requires no application API key and provides roads, blocks, and place labels. The frontend will load it directly over the network; this design intentionally does not provide an offline street-map fallback.

The existing MapLibre adapter remains the owner of map instances, sources, layers, listeners, and cleanup. The UI continues to emit intent and render application state; it does not calculate incidents or priority.

### Overlay hierarchy

1. Street basemap: recognizable roads and labels.
2. Density layer: translucent and visually subordinate to street labels.
3. Incident radius: low-opacity fill with a restrained line.
4. Incident centroid: clear point marker.
5. Selected incident: dark outer stroke and increased radius, readable independently of heat color.

### Heat palette

Use a color-blind-conscious progression with sufficient contrast against the street map:

- low: `#2F80ED` (clear blue);
- moderate: `#22B8A7` (teal);
- elevated: `#F2C94C` (amber);
- high: `#F2994A` (orange);
- critical density: `#D64545` (red).

The heat layer uses controlled opacity so road geometry and labels remain visible. Color communicates density only; operational priority keeps its existing separate semantics.

### Legend and map states

Add a compact, keyboard-inert legend labeled “Report density” with Low and High endpoints and the same gradient as the map. Place it inside the map frame without obscuring primary controls. Loading, degraded, and retry behavior remain explicit. External style-load failures use the existing degraded-map recovery path and do not invent incident data.

## Control Direction

Preserve the existing CivicPulse typography, spacing tokens, canvas colors, and restrained municipal-ledger character. Do not introduce a new component library.

Create a small reusable control vocabulary through existing CSS tokens/classes:

- primary: dark filled action for the main form submission;
- secondary: bordered, lightly tinted action for “Upload photo” and “Retry upload”;
- danger/quiet: restrained red text and border for “Remove photo”, without a large destructive fill;
- disabled: reduced contrast plus non-interactive cursor;
- focus: visible two-layer focus ring with adequate contrast;
- hover/active: subtle background and one-pixel visual movement, disabled under reduced-motion preferences.

The native file input remains accessible but is visually represented by a labeled button. The real input stays available to assistive technology and keyboard activation. Button text remains explicit: Upload photo, Retry upload, Remove photo, and Submit report.

## Responsive and Accessibility Requirements

- Maintain a minimum 44 px interactive target height on touch layouts.
- Preserve visible keyboard focus for all controls.
- Do not rely on color alone for selection or destructive meaning.
- Keep map legend text readable at narrow widths and avoid covering map attribution.
- Respect `prefers-reduced-motion`.
- Keep semantic `button`, `label`, and file-input behavior; no clickable generic elements.

## Data and Privacy Boundaries

OpenFreeMap receives ordinary map-style and tile requests plus viewport coordinates. Complaint text, reporter data, photo identifiers, review data, and incident membership are never included in basemap requests. No provider token or secret is added to the repository.

## Testing and Verification

Automated coverage will verify:

- the OpenFreeMap style URL is used by the adapter;
- density colors and selected-point stroke/radius are configured as specified;
- legend labels render;
- upload, retry, remove, focus, and disabled states retain semantic controls;
- existing map lifecycle cleanup, selection, and degraded-state tests remain green;
- full frontend `pnpm run check` passes.

Live browser verification will confirm streets and labels render, heat colors remain distinguishable, the legend does not cover controls/attribution, keyboard focus is visible, and upload/retry/remove controls no longer look like unstyled browser defaults.

## Delivery Boundary

This is one frontend-only implementation slice. It will be committed and reviewed before the photo-evidence branch is merged into `master`.
