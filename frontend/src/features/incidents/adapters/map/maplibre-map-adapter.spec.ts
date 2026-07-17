import { describe, expect, it } from "vitest"

import type { IncidentMapView, MapLifecycleState } from "../../application/incident-map-port"
import type { HeatCell, HeatmapMode } from "../../domain/heatmap"
import type { IncidentSummary } from "../../domain/incident"
import {
  createMapLibreIncidentMapRenderer,
  type MapFactory,
  type MapLike,
} from "./maplibre-map-adapter"
import { FALLBACK_MAP_STYLE } from "./fallback-style"

type Listener = (...args: unknown[]) => void

const incident: IncidentSummary = {
  incidentId: "incident-1",
  status: "confirmed",
  categories: ["flooding"],
  priority: { level: "high", reasons: [], policyVersion: "priority-v1" },
  confirmedReportCount: 2,
  pendingCandidateCount: 0,
  centroid: { latitude: 1.3, longitude: 103.8 },
  radiusMetres: 100,
  earliestReportedAt: "2026-07-16T01:00:00Z",
  latestReportedAt: "2026-07-16T02:00:00Z",
  conflictReasons: [],
}

function cells(overrides: Partial<HeatCell> = {}): readonly HeatCell[] {
  return [
    {
      longitude: 103.8,
      latitude: 1.3,
      intensity: 1,
      dominantCategory: "flooding",
      ...overrides,
    },
  ]
}

function view(overrides: Partial<IncidentMapView> = {}): IncidentMapView {
  return {
    incidents: [incident],
    cells: cells(),
    mode: { kind: "all" },
    selectedIncidentId: null,
    hoveredIncidentId: null,
    ...overrides,
  }
}

function fakeMap(styleLoaded = true) {
  const listeners = new Map<string, Set<Listener>>()
  const calls: Array<{ method: string; args: unknown[] }> = []
  const sources = new Map<string, unknown>()
  const layers = new Map<string, unknown>()
  const map: MapLike = {
    isStyleLoaded() {
      return styleLoaded
    },
    on(event: string, layerOrListener: string | Listener, maybeListener?: Listener) {
      const listener = typeof layerOrListener === "string" ? maybeListener : layerOrListener
      if (listener === undefined) {
        throw new Error("A map listener is required")
      }
      calls.push({ method: "on", args: [event, layerOrListener, maybeListener] })
      const eventListeners = listeners.get(event) ?? new Set<Listener>()
      eventListeners.add(listener)
      listeners.set(event, eventListeners)
    },
    off(event: string, layerOrListener: string | Listener, maybeListener?: Listener) {
      const listener = typeof layerOrListener === "string" ? maybeListener : layerOrListener
      if (listener === undefined) {
        throw new Error("A map listener is required")
      }
      calls.push({ method: "off", args: [event, layerOrListener, maybeListener] })
      listeners.get(event)?.delete(listener)
    },
    addSource(id: string, source: unknown) {
      calls.push({ method: "addSource", args: [id, source] })
      sources.set(id, source)
    },
    removeSource(id: string) {
      calls.push({ method: "removeSource", args: [id] })
      sources.delete(id)
    },
    setStyle(style: unknown) {
      calls.push({ method: "setStyle", args: [style] })
    },
    addLayer(layer: unknown) {
      calls.push({ method: "addLayer", args: [layer] })
      if (typeof layer === "object" && layer !== null && "id" in layer) {
        layers.set(String(layer.id), layer)
      }
    },
    removeLayer(id: string) {
      calls.push({ method: "removeLayer", args: [id] })
      layers.delete(id)
    },
    resize() {
      calls.push({ method: "resize", args: [] })
    },
    remove() {
      calls.push({ method: "remove", args: [] })
    },
  }
  return {
    map,
    calls,
    sources,
    layers,
    emit(event: string, ...args: unknown[]) {
      for (const listener of listeners.get(event) ?? []) {
        listener(...args)
      }
    },
  }
}

function factoryFor(fake: ReturnType<typeof fakeMap>, options: { style?: unknown }[] = []): MapFactory {
  return (mapOptions) => {
    options.push(mapOptions)
    return fake.map
  }
}

const allMode: HeatmapMode = { kind: "all" }

describe("createMapLibreIncidentMapRenderer", () => {
  it("mounts an inline fallback style without network tiles", () => {
    const fake = fakeMap()
    const options: { style?: unknown }[] = []
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake, options) })

    renderer.mount(document.createElement("div"))

    expect(options[0]?.style).toEqual(FALLBACK_MAP_STYLE)
    expect(FALLBACK_MAP_STYLE.sources).toEqual({})
    expect(JSON.stringify(FALLBACK_MAP_STYLE)).not.toMatch(/https?:\/\//)
  })

  it("adds one deterministic GeoJSON source and disposes listeners", () => {
    const fake = fakeMap()
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))

    renderer.render(view({ mode: allMode }))

    const sourceAdds = fake.calls.filter((call) => call.method === "addSource")
    expect(sourceAdds).toHaveLength(3)
    expect(sourceAdds[0]?.args[0]).toBe("civicpulse-incident-density")
    expect(sourceAdds[0]?.args[1]).toMatchObject({ type: "geojson" })

    renderer.dispose()

    expect(fake.calls.filter((call) => call.method === "off")).toHaveLength(7)
    expect(fake.calls.filter((call) => call.method === "removeLayer")).toHaveLength(5)
    expect(fake.calls.filter((call) => call.method === "removeSource")).toHaveLength(3)
    expect(fake.calls.filter((call) => call.method === "remove")).toHaveLength(1)
  })

  it("renders a single-category heat layer with its category color", () => {
    const fake = fakeMap()
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))

    const strategy = renderer.render(view({
      cells: cells({ dominantCategory: "flooding" }),
      mode: { kind: "category", category: "flooding" },
    }))

    expect(strategy).toBe("category-heat")
    const layers = fake.calls.filter((call) => call.method === "addLayer")
    expect(layers).toHaveLength(5)
    expect(layers.find((layer) => layer.args[0] && typeof layer.args[0] === "object" && "id" in layer.args[0] && layer.args[0].id === "civicpulse-incident-category-heat")?.args[0]).toMatchObject({
      id: "civicpulse-incident-category-heat",
      type: "heatmap",
      filter: ["==", ["get", "dominantCategory"], "flooding"],
      paint: {
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0,
          "rgba(0, 0, 0, 0)",
          0.01,
          "rgba(22, 119, 168, 0.25)",
          0.35,
          "rgba(22, 119, 168, 0.65)",
          1,
          "#1677a8",
        ],
      },
    })
  })

  it("returns neutral fallback for All mode when exact category heat is unavailable", () => {
    const fake = fakeMap()
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))

    const strategy = renderer.render(view({ mode: allMode }))

    expect(strategy).toBe("neutral-density")
    expect(fake.calls.filter((call) => call.method === "addLayer")).toHaveLength(5)
    expect(fake.calls.filter((call) => call.method === "addLayer").find((call) => call.args[0] && typeof call.args[0] === "object" && "id" in call.args[0] && call.args[0].id === "civicpulse-incident-neutral-heat")?.args[0]).toMatchObject({
      id: "civicpulse-incident-neutral-heat",
      type: "heatmap",
      paint: {
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0,
          "rgba(0, 0, 0, 0)",
          0.01,
          "rgba(100, 116, 139, 0.25)",
          0.35,
          "rgba(100, 116, 139, 0.65)",
          1,
          "#64748b",
        ],
      },
    })
  })

  it("does not create a category layer stack that can blend overlapping colors", () => {
    const fake = fakeMap()
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))

    renderer.render(view({
      cells: [
        ...cells({ dominantCategory: "flooding" }),
        ...cells({ longitude: 103.81, dominantCategory: "rubbish" }),
      ],
      mode: allMode,
    }))

    const layers = fake.calls.filter((call) => call.method === "addLayer")
    expect(layers).toHaveLength(5)
    expect(layers.find((layer) => layer.args[0] && typeof layer.args[0] === "object" && "id" in layer.args[0] && layer.args[0].id === "civicpulse-incident-neutral-heat")?.args[0]).toMatchObject({ id: "civicpulse-incident-neutral-heat" })
  })

  it("queues the latest render until the MapLibre style is loaded", () => {
    const fake = fakeMap(false)
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))

    const strategy = renderer.render(view({ mode: { kind: "category", category: "flooding" } }))

    expect(strategy).toBe("category-heat")
    expect(fake.calls.filter((call) => call.method === "addSource")).toHaveLength(0)
    expect(fake.calls.filter((call) => call.method === "addLayer")).toHaveLength(0)

    fake.emit("load")

    expect(fake.calls.filter((call) => call.method === "addSource")).toHaveLength(3)
    expect(fake.calls.filter((call) => call.method === "addLayer")).toHaveLength(5)
  })

  it("clears a queued render when disposed before the style loads", () => {
    const fake = fakeMap(false)
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))
    renderer.render(view({ mode: allMode }))
    renderer.dispose()

    fake.emit("load")

    expect(fake.calls.filter((call) => call.method === "addSource")).toHaveLength(0)
    expect(fake.calls.filter((call) => call.method === "addLayer")).toHaveLength(0)
  })

  it("renders separate affected-area and centroid sources with selected styling", () => {
    const fake = fakeMap()
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))

    renderer.render(view({ selectedIncidentId: "incident-1" }))

    const sourceAdds = fake.calls.filter((call) => call.method === "addSource")
    expect(sourceAdds.map((call) => call.args[0])).toEqual([
      "civicpulse-incident-density",
      "civicpulse-incident-radius",
      "civicpulse-incident-centroids",
    ])
    expect(sourceAdds[1]?.args[1]).toMatchObject({
      type: "geojson",
      data: { features: [{ geometry: { type: "Polygon" } }] },
    })
    expect(sourceAdds[2]?.args[1]).toMatchObject({
      type: "geojson",
      data: { features: [{ geometry: { type: "Point" }, properties: { selected: true } }] },
    })
    expect(fake.calls.filter((call) => call.method === "addLayer").map((call) => call.args[0])).toEqual([
      expect.objectContaining({ id: "civicpulse-incident-neutral-heat" }),
      expect.objectContaining({ id: "civicpulse-incident-radius-fill" }),
      expect.objectContaining({ id: "civicpulse-incident-radius-line" }),
      expect.objectContaining({ id: "civicpulse-incident-centroids" }),
      expect.objectContaining({ id: "civicpulse-incident-selected" }),
    ])
  })

  it("emits map selection and preview events for incident centroids", () => {
    const fake = fakeMap()
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    const selections: string[] = []
    const previews: Array<string | null> = []
    renderer.onIncidentSelect((incidentId) => selections.push(incidentId))
    renderer.onIncidentPreview((incidentId) => previews.push(incidentId))
    renderer.mount(document.createElement("div"))
    renderer.render(view())

    fake.emit("click", { features: [{ properties: { incidentId: "incident-1" } }] })
    fake.emit("mouseenter", { features: [{ properties: { incidentId: "incident-1" } }] })
    fake.emit("mouseleave")

    expect(selections).toEqual(["incident-1"])
    expect(previews).toEqual(["incident-1", null])
  })

  it("degrades on map errors and recovers the last view through one style reload", () => {
    const fake = fakeMap()
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    const states: MapLifecycleState[] = []
    renderer.onLifecycleChange((state) => states.push(state))
    renderer.mount(document.createElement("div"))
    renderer.render(view())

    fake.emit("error")
    renderer.retry()
    fake.emit("style.load")

    expect(states).toEqual(["loading", "ready", "degraded", "recovering", "ready"])
    expect(fake.calls.filter((call) => call.method === "setStyle")).toHaveLength(1)
    expect(fake.calls.filter((call) => call.method === "addSource").length).toBeGreaterThanOrEqual(6)
    expect(fake.calls.filter((call) => call.method === "remove")).toHaveLength(0)
  })
})
