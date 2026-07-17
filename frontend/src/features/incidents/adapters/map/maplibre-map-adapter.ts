import type { HeatCell, HeatmapMode } from "../../domain/heatmap"
import { Map as MapLibreMap, type MapOptions } from "maplibre-gl"
import { FALLBACK_MAP_STYLE } from "./fallback-style"
import type { IncidentMapRenderer } from "../../application/incident-map-port"

export interface MapLike {
  isStyleLoaded(): boolean
  on(event: string, listener: (...args: unknown[]) => void): void
  off(event: string, listener: (...args: unknown[]) => void): void
  addSource(id: string, source: unknown): void
  removeSource(id: string): void
  addLayer(layer: unknown): void
  removeLayer(id: string): void
  resize(): void
  remove(): void
}

export interface MapFactoryOptions {
  readonly container: HTMLElement
  readonly style: unknown
  readonly center: readonly [number, number]
  readonly zoom: number
  readonly attributionControl: false
}

export type MapFactory = (options: MapFactoryOptions) => MapLike

export interface MapLibreIncidentMapRendererOptions {
  readonly createMap?: MapFactory
  readonly center?: readonly [number, number]
  readonly zoom?: number
}

const SOURCE_ID = "civicpulse-incident-density"
const NEUTRAL_LAYER_ID = "civicpulse-incident-neutral-heat"
const CATEGORY_LAYER_ID = "civicpulse-incident-category-heat"

const CATEGORY_COLORS = {
  flooding: "#1677a8",
  blocked_drain: "#267f86",
  pothole: "#a4772d",
  rubbish: "#883f4a",
  street_light: "#5b5b88",
  other: "#64748b",
} as const

const NEUTRAL_COLOR = "#64748b"

interface GeoJsonFeature {
  readonly type: "Feature"
  readonly geometry: { readonly type: "Point"; readonly coordinates: readonly [number, number] }
  readonly properties: { readonly intensity: number; readonly dominantCategory: string }
}

function featureCollection(cells: readonly HeatCell[]) {
  return {
    type: "FeatureCollection" as const,
    features: cells.map<GeoJsonFeature>((cell) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [cell.longitude, cell.latitude] },
      properties: { intensity: cell.intensity, dominantCategory: cell.dominantCategory },
    })),
  }
}

function heatLayer(id: string, color: string, filter?: readonly unknown[]) {
  return {
    id,
    type: "heatmap" as const,
    ...(filter ? { filter } : {}),
    source: SOURCE_ID,
    paint: {
      "heatmap-weight": ["get", "intensity"],
      "heatmap-intensity": 1,
      "heatmap-radius": 24,
      "heatmap-opacity": 0.82,
      "heatmap-color": color,
    },
  }
}

export function createMapLibreIncidentMapRenderer(
  options: MapLibreIncidentMapRendererOptions,
): IncidentMapRenderer {
  let map: MapLike | null = null
  let mounted = false
  let styleReady = false
  let activeLayerId: string | null = null
  let sourceAdded = false
  let queuedRender: { cells: readonly HeatCell[]; mode: HeatmapMode } | null = null

  const onLoad = () => {
    styleReady = true
    if (queuedRender !== null && map !== null && mounted) {
      const nextRender = queuedRender
      queuedRender = null
      renderNow(nextRender.cells, nextRender.mode)
    }
  }
  const onError = () => undefined
  const onResize = () => undefined

  function mount(container: HTMLElement): void {
    if (map !== null) {
      return
    }
    const createMap = options.createMap ?? defaultMapFactory
    map = createMap({
      container,
      style: FALLBACK_MAP_STYLE,
      center: options.center ?? [103.8198, 1.3521],
      zoom: options.zoom ?? 11,
      attributionControl: false,
    })
    map.on("load", onLoad)
    map.on("error", onError)
    map.on("resize", onResize)
    styleReady = map.isStyleLoaded()
    mounted = true
  }

  function renderNow(cells: readonly HeatCell[], mode: HeatmapMode) {
    if (map === null || !mounted) {
      throw new Error("Incident map renderer must be mounted before rendering")
    }
    if (activeLayerId !== null) {
      map.removeLayer(activeLayerId)
      activeLayerId = null
    }
    if (sourceAdded) {
      map.removeSource(SOURCE_ID)
      sourceAdded = false
    }

    map.addSource(SOURCE_ID, { type: "geojson", data: featureCollection(cells) })
    sourceAdded = true

    if (mode.kind === "all") {
      activeLayerId = NEUTRAL_LAYER_ID
      map.addLayer(heatLayer(NEUTRAL_LAYER_ID, NEUTRAL_COLOR))
      return "neutral-density" as const
    }

    activeLayerId = CATEGORY_LAYER_ID
    map.addLayer(
      heatLayer(CATEGORY_LAYER_ID, CATEGORY_COLORS[mode.category], [
        "==",
        ["get", "dominantCategory"],
        mode.category,
      ]),
    )
    return "category-heat" as const
  }

  function render(cells: readonly HeatCell[], mode: HeatmapMode) {
    if (map === null || !mounted) {
      throw new Error("Incident map renderer must be mounted before rendering")
    }
    if (!styleReady) {
      queuedRender = { cells: [...cells], mode }
      return mode.kind === "all" ? ("neutral-density" as const) : ("category-heat" as const)
    }
    return renderNow(cells, mode)
  }

  function resize(): void {
    map?.resize()
  }

  function dispose(): void {
    if (map === null) {
      return
    }
    map.off("load", onLoad)
    map.off("error", onError)
    map.off("resize", onResize)
    if (activeLayerId !== null) {
      map.removeLayer(activeLayerId)
    }
    if (sourceAdded) {
      map.removeSource(SOURCE_ID)
    }
    map.remove()
    map = null
    queuedRender = null
    activeLayerId = null
    sourceAdded = false
    mounted = false
  }

  return { mount, render, resize, dispose }
}

function defaultMapFactory(options: MapFactoryOptions): MapLike {
  return new MapLibreMap(options as unknown as MapOptions) as unknown as MapLike
}
