import { describe, expect, it } from "vitest"

import type { HeatCell, HeatmapMode } from "../../domain/heatmap"
import {
  createMapLibreIncidentMapRenderer,
  type MapFactory,
  type MapLike,
} from "./maplibre-map-adapter"
import { FALLBACK_MAP_STYLE } from "./fallback-style"

type Listener = (...args: unknown[]) => void

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

function fakeMap(styleLoaded = true) {
  const listeners = new Map<string, Set<Listener>>()
  const calls: Array<{ method: string; args: unknown[] }> = []
  const sources = new Map<string, unknown>()
  const layers = new Map<string, unknown>()
  const map: MapLike = {
    isStyleLoaded() {
      return styleLoaded
    },
    on(event: string, listener: Listener) {
      calls.push({ method: "on", args: [event, listener] })
      const eventListeners = listeners.get(event) ?? new Set<Listener>()
      eventListeners.add(listener)
      listeners.set(event, eventListeners)
    },
    off(event: string, listener: Listener) {
      calls.push({ method: "off", args: [event, listener] })
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
    emit(event: string) {
      for (const listener of listeners.get(event) ?? []) {
        listener()
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

    renderer.render(cells(), allMode)

    const sourceAdds = fake.calls.filter((call) => call.method === "addSource")
    expect(sourceAdds).toHaveLength(1)
    expect(sourceAdds[0]?.args[0]).toBe("civicpulse-incident-density")
    expect(sourceAdds[0]?.args[1]).toMatchObject({ type: "geojson" })

    renderer.dispose()

    expect(fake.calls.filter((call) => call.method === "off")).toHaveLength(3)
    expect(fake.calls.filter((call) => call.method === "removeLayer")).toHaveLength(1)
    expect(fake.calls.filter((call) => call.method === "removeSource")).toHaveLength(1)
    expect(fake.calls.filter((call) => call.method === "remove")).toHaveLength(1)
  })

  it("renders a single-category heat layer with its category color", () => {
    const fake = fakeMap()
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))

    const strategy = renderer.render(cells({ dominantCategory: "flooding" }), {
      kind: "category",
      category: "flooding",
    })

    expect(strategy).toBe("category-heat")
    const layers = fake.calls.filter((call) => call.method === "addLayer")
    expect(layers).toHaveLength(1)
    expect(layers[0]?.args[0]).toMatchObject({
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
          "#1677a8",
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

    const strategy = renderer.render(cells(), allMode)

    expect(strategy).toBe("neutral-density")
    expect(fake.calls.filter((call) => call.method === "addLayer")).toHaveLength(1)
    expect(fake.calls.at(-1)?.args[0]).toMatchObject({
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
          "#64748b",
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

    renderer.render(
      [
        ...cells({ dominantCategory: "flooding" }),
        ...cells({ longitude: 103.81, dominantCategory: "rubbish" }),
      ],
      allMode,
    )

    const layers = fake.calls.filter((call) => call.method === "addLayer")
    expect(layers).toHaveLength(1)
    expect(layers[0]?.args[0]).toMatchObject({ id: "civicpulse-incident-neutral-heat" })
  })

  it("queues the latest render until the MapLibre style is loaded", () => {
    const fake = fakeMap(false)
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))

    const strategy = renderer.render(cells(), { kind: "category", category: "flooding" })

    expect(strategy).toBe("category-heat")
    expect(fake.calls.filter((call) => call.method === "addSource")).toHaveLength(0)
    expect(fake.calls.filter((call) => call.method === "addLayer")).toHaveLength(0)

    fake.emit("load")

    expect(fake.calls.filter((call) => call.method === "addSource")).toHaveLength(1)
    expect(fake.calls.filter((call) => call.method === "addLayer")).toHaveLength(1)
  })

  it("clears a queued render when disposed before the style loads", () => {
    const fake = fakeMap(false)
    const renderer = createMapLibreIncidentMapRenderer({ createMap: factoryFor(fake) })
    renderer.mount(document.createElement("div"))
    renderer.render(cells(), allMode)
    renderer.dispose()

    fake.emit("load")

    expect(fake.calls.filter((call) => call.method === "addSource")).toHaveLength(0)
    expect(fake.calls.filter((call) => call.method === "addLayer")).toHaveLength(0)
  })
})
