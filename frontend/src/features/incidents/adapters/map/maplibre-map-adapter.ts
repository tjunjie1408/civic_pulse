import { Map as MapLibreMap, type MapOptions } from "maplibre-gl"

import type {
  IncidentMapPreviewListener,
  IncidentMapRenderer,
  IncidentMapSelectionListener,
  IncidentMapView,
  MapLifecycleListener,
  MapRenderStrategy,
  MapLifecycleState,
} from "../../application/incident-map-port"
import type { HeatCell } from "../../domain/heatmap"
import { projectAffectedAreas } from "../../domain/radius-overlay"
import { FALLBACK_MAP_STYLE } from "./fallback-style"

type MapListener = (...args: unknown[]) => void

export interface MapLike {
  isStyleLoaded(): boolean
  on(event: string, listener: MapListener): void
  on(event: string, layerId: string, listener: MapListener): void
  off(event: string, listener: MapListener): void
  off(event: string, layerId: string, listener: MapListener): void
  addSource(id: string, source: unknown): void
  removeSource(id: string): void
  setStyle(style: unknown): void
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
  readonly style?: unknown
}

const SOURCE_ID = "civicpulse-incident-density"
const RADIUS_SOURCE_ID = "civicpulse-incident-radius"
const CENTROID_SOURCE_ID = "civicpulse-incident-centroids"
const NEUTRAL_LAYER_ID = "civicpulse-incident-neutral-heat"
const CATEGORY_LAYER_ID = "civicpulse-incident-category-heat"
const RADIUS_FILL_LAYER_ID = "civicpulse-incident-radius-fill"
const RADIUS_LINE_LAYER_ID = "civicpulse-incident-radius-line"
const CENTROID_LAYER_ID = "civicpulse-incident-centroids"
const SELECTED_LAYER_ID = "civicpulse-incident-selected"

const CATEGORY_COLORS = {
  flooding: "#1677a8",
  blocked_drain: "#267f86",
  pothole: "#a4772d",
  rubbish: "#883f4a",
  street_light: "#5b5b88",
  other: "#64748b",
} as const

const NEUTRAL_COLOR = "#64748b"

interface HeatGeoJsonFeature {
  readonly type: "Feature"
  readonly geometry: { readonly type: "Point"; readonly coordinates: readonly [number, number] }
  readonly properties: { readonly intensity: number; readonly dominantCategory: string }
}

interface MapFeatureEvent {
  readonly features?: readonly { readonly properties?: Readonly<Record<string, unknown>> }[]
}

function heatFeatureCollection(cells: readonly HeatCell[]) {
  return {
    type: "FeatureCollection" as const,
    features: cells.map<HeatGeoJsonFeature>((cell) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [cell.longitude, cell.latitude] },
      properties: { intensity: cell.intensity, dominantCategory: cell.dominantCategory },
    })),
  }
}

function radiusFeatureCollection(view: IncidentMapView) {
  const projected = projectAffectedAreas(view.incidents)
  return {
    ...projected,
    features: projected.features.map((feature) => ({
      ...feature,
      properties: {
        ...feature.properties,
        selected: feature.properties.incidentId === view.selectedIncidentId,
      },
    })),
  }
}

function centroidFeatureCollection(view: IncidentMapView) {
  return {
    type: "FeatureCollection" as const,
    features: view.incidents.map((incident) => ({
      type: "Feature" as const,
      geometry: {
        type: "Point" as const,
        coordinates: [incident.centroid.longitude, incident.centroid.latitude] as [number, number],
      },
      properties: {
        incidentId: incident.incidentId,
        selected: incident.incidentId === view.selectedIncidentId,
        hovered: incident.incidentId === view.hoveredIncidentId,
      },
    })),
  }
}

function withAlpha(hexColor: string, alpha: number): string {
  const red = Number.parseInt(hexColor.slice(1, 3), 16)
  const green = Number.parseInt(hexColor.slice(3, 5), 16)
  const blue = Number.parseInt(hexColor.slice(5, 7), 16)
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
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
      "heatmap-color": [
        "interpolate",
        ["linear"],
        ["heatmap-density"],
        0,
        "rgba(0, 0, 0, 0)",
        0.01,
        withAlpha(color, 0.25),
        0.35,
        withAlpha(color, 0.65),
        1,
        color,
      ],
    },
  }
}

function mapFeatureIncidentId(event: unknown): string | null {
  if (typeof event !== "object" || event === null || !("features" in event)) {
    return null
  }
  const features = (event as MapFeatureEvent).features
  const incidentId = features?.[0]?.properties?.incidentId
  return typeof incidentId === "string" ? incidentId : null
}

export function createMapLibreIncidentMapRenderer(
  options: MapLibreIncidentMapRendererOptions,
): IncidentMapRenderer {
  let map: MapLike | null = null
  let mounted = false
  let styleReady = false
  const renderedLayerIds = new Set<string>()
  const renderedSourceIds = new Set<string>()
  let queuedView: IncidentMapView | null = null
  let lastView: IncidentMapView | null = null
  let lifecycleState: MapLifecycleState = "loading"
  const selectionListeners = new Set<IncidentMapSelectionListener>()
  const previewListeners = new Set<IncidentMapPreviewListener>()
  const lifecycleListeners = new Set<MapLifecycleListener>()

  const emitLifecycle = (next: MapLifecycleState): void => {
    if (lifecycleState === next) {
      return
    }
    lifecycleState = next
    for (const listener of lifecycleListeners) {
      listener(next)
    }
  }

  const onLoad: MapListener = () => {
    styleReady = true
    emitLifecycle("ready")
    if (queuedView !== null && map !== null && mounted) {
      const nextView = queuedView
      queuedView = null
      renderNow(nextView)
    }
  }
  const onStyleLoad: MapListener = () => {
    if (!mounted || lifecycleState !== "recovering" || map === null) {
      return
    }
    styleReady = true
    renderedLayerIds.clear()
    renderedSourceIds.clear()
    if (lastView !== null) {
      renderNow(lastView)
    }
    emitLifecycle("ready")
  }
  const onError: MapListener = () => {
    styleReady = false
    emitLifecycle("degraded")
  }
  const onResize: MapListener = () => undefined
  const onIncidentClick: MapListener = (event) => {
    const incidentId = mapFeatureIncidentId(event)
    if (incidentId !== null) {
      for (const listener of selectionListeners) {
        listener(incidentId)
      }
    }
  }
  const onIncidentEnter: MapListener = (event) => {
    const incidentId = mapFeatureIncidentId(event)
    for (const listener of previewListeners) {
      listener(incidentId)
    }
  }
  const onIncidentLeave: MapListener = () => {
    for (const listener of previewListeners) {
      listener(null)
    }
  }

  function mount(container: HTMLElement): void {
    if (map !== null) {
      return
    }
    const createMap = options.createMap ?? defaultMapFactory
    map = createMap({
      container,
      style: options.style ?? FALLBACK_MAP_STYLE,
      center: options.center ?? [101.52, 3.08],
      zoom: options.zoom ?? 11,
      attributionControl: false,
    })
    map.on("load", onLoad)
    map.on("style.load", onStyleLoad)
    map.on("error", onError)
    map.on("resize", onResize)
    map.on("click", CENTROID_LAYER_ID, onIncidentClick)
    map.on("mouseenter", CENTROID_LAYER_ID, onIncidentEnter)
    map.on("mouseleave", CENTROID_LAYER_ID, onIncidentLeave)
    styleReady = map.isStyleLoaded()
    mounted = true
    if (styleReady) {
      emitLifecycle("ready")
    }
  }

  function clearRenderedResources(): void {
    if (map === null) {
      return
    }
    for (const layerId of renderedLayerIds) {
      map.removeLayer(layerId)
    }
    for (const sourceId of renderedSourceIds) {
      map.removeSource(sourceId)
    }
    renderedLayerIds.clear()
    renderedSourceIds.clear()
  }

  function renderNow(view: IncidentMapView): MapRenderStrategy {
    if (map === null || !mounted) {
      throw new Error("Incident map renderer must be mounted before rendering")
    }
    clearRenderedResources()
    map.addSource(SOURCE_ID, { type: "geojson", data: heatFeatureCollection(view.cells) })
    renderedSourceIds.add(SOURCE_ID)
    map.addSource(RADIUS_SOURCE_ID, { type: "geojson", data: radiusFeatureCollection(view) })
    renderedSourceIds.add(RADIUS_SOURCE_ID)
    map.addSource(CENTROID_SOURCE_ID, { type: "geojson", data: centroidFeatureCollection(view) })
    renderedSourceIds.add(CENTROID_SOURCE_ID)
    if (view.mode.kind === "all") {
      map.addLayer(heatLayer(NEUTRAL_LAYER_ID, NEUTRAL_COLOR))
      renderedLayerIds.add(NEUTRAL_LAYER_ID)
    } else {
      map.addLayer(
        heatLayer(CATEGORY_LAYER_ID, CATEGORY_COLORS[view.mode.category], [
          "==",
          ["get", "dominantCategory"],
          view.mode.category,
        ]),
      )
      renderedLayerIds.add(CATEGORY_LAYER_ID)
    }

    map.addLayer({
      id: RADIUS_FILL_LAYER_ID,
      type: "fill" as const,
      source: RADIUS_SOURCE_ID,
      paint: { "fill-color": NEUTRAL_COLOR, "fill-opacity": 0.06 },
    })
    renderedLayerIds.add(RADIUS_FILL_LAYER_ID)
    map.addLayer({
      id: RADIUS_LINE_LAYER_ID,
      type: "line" as const,
      source: RADIUS_SOURCE_ID,
      paint: {
        "line-color": NEUTRAL_COLOR,
        "line-opacity": 0.5,
        "line-width": ["case", ["get", "selected"], 3, 1],
      },
    })
    renderedLayerIds.add(RADIUS_LINE_LAYER_ID)
    map.addLayer({
      id: CENTROID_LAYER_ID,
      type: "circle" as const,
      source: CENTROID_SOURCE_ID,
      paint: {
        "circle-color": NEUTRAL_COLOR,
        "circle-radius": ["case", ["get", "hovered"], 7, 5],
        "circle-opacity": 0.9,
      },
    })
    renderedLayerIds.add(CENTROID_LAYER_ID)
    map.addLayer({
      id: SELECTED_LAYER_ID,
      type: "circle" as const,
      source: CENTROID_SOURCE_ID,
      filter: ["==", ["get", "selected"], true],
      paint: {
        "circle-color": "#171a1c",
        "circle-radius": 9,
        "circle-opacity": 0.95,
      },
    })
    renderedLayerIds.add(SELECTED_LAYER_ID)
    lastView = view
    return view.mode.kind === "all" ? "neutral-density" : "category-heat"
  }

  function render(view: IncidentMapView): MapRenderStrategy {
    if (map === null || !mounted) {
      throw new Error("Incident map renderer must be mounted before rendering")
    }
    lastView = view
    if (!styleReady) {
      queuedView = view
      return view.mode.kind === "all" ? "neutral-density" : "category-heat"
    }
    return renderNow(view)
  }

  function resize(): void {
    map?.resize()
  }

  function onIncidentSelect(listener: IncidentMapSelectionListener): () => void {
    selectionListeners.add(listener)
    return () => selectionListeners.delete(listener)
  }

  function onIncidentPreview(listener: IncidentMapPreviewListener): () => void {
    previewListeners.add(listener)
    return () => previewListeners.delete(listener)
  }

  function onLifecycleChange(listener: MapLifecycleListener): () => void {
    lifecycleListeners.add(listener)
    listener(lifecycleState)
    return () => lifecycleListeners.delete(listener)
  }

  function retry(): void {
    if (map === null || lifecycleState !== "degraded") {
      return
    }
    styleReady = false
    emitLifecycle("recovering")
    map.setStyle(options.style ?? FALLBACK_MAP_STYLE)
  }

  function dispose(): void {
    if (map === null) {
      return
    }
    map.off("load", onLoad)
    map.off("style.load", onStyleLoad)
    map.off("error", onError)
    map.off("resize", onResize)
    map.off("click", CENTROID_LAYER_ID, onIncidentClick)
    map.off("mouseenter", CENTROID_LAYER_ID, onIncidentEnter)
    map.off("mouseleave", CENTROID_LAYER_ID, onIncidentLeave)
    if (styleReady) {
      clearRenderedResources()
    }
    map.remove()
    map = null
    queuedView = null
    lastView = null
    mounted = false
    styleReady = false
    selectionListeners.clear()
    previewListeners.clear()
    lifecycleListeners.clear()
  }

  return {
    mount,
    render,
    resize,
    onIncidentSelect,
    onIncidentPreview,
    onLifecycleChange,
    retry,
    dispose,
  }
}

function defaultMapFactory(options: MapFactoryOptions): MapLike {
  return new MapLibreMap(options as unknown as MapOptions) as unknown as MapLike
}
