import type { HeatCell, HeatmapMode } from "../domain/heatmap"
import type { IncidentSummary } from "../domain/incident"

export type MapRenderStrategy = "category-heat" | "neutral-density"

export type MapLifecycleState = "loading" | "ready" | "degraded" | "recovering"

export interface IncidentMapView {
  readonly incidents: readonly IncidentSummary[]
  readonly cells: readonly HeatCell[]
  readonly mode: HeatmapMode
  readonly selectedIncidentId: string | null
  readonly hoveredIncidentId: string | null
}

export type IncidentMapSelectionListener = (incidentId: string) => void
export type IncidentMapPreviewListener = (incidentId: string | null) => void
export type MapLifecycleListener = (state: MapLifecycleState) => void

export interface IncidentMapRenderer {
  mount(container: HTMLElement): void
  render(view: IncidentMapView): MapRenderStrategy
  resize(): void
  onIncidentSelect(listener: IncidentMapSelectionListener): () => void
  onIncidentPreview(listener: IncidentMapPreviewListener): () => void
  onLifecycleChange(listener: MapLifecycleListener): () => void
  retry(): void
  dispose(): void
}
