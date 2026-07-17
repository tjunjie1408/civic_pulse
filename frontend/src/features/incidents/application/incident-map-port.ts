import type { HeatCell, HeatmapMode } from "../domain/heatmap"

export type MapRenderStrategy = "category-heat" | "neutral-density"

export interface IncidentMapRenderer {
  mount(container: HTMLElement): void
  render(cells: readonly HeatCell[], mode: HeatmapMode): MapRenderStrategy
  resize(): void
  dispose(): void
}
