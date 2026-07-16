import type { IncidentCategory, IncidentSummary, OperationalPriorityLevel } from "./incident"

export type HeatmapMode =
  | { readonly kind: "all" }
  | { readonly kind: "category"; readonly category: IncidentCategory }

export interface HeatCell {
  readonly longitude: number
  readonly latitude: number
  readonly intensity: number
  readonly dominantCategory: IncidentCategory
}

export const HEATMAP_CELL_SIZE_DEGREES = 0.001

export const HEATMAP_CATEGORY_ORDER: readonly IncidentCategory[] = Object.freeze([
  "flooding",
  "blocked_drain",
  "pothole",
  "rubbish",
  "street_light",
  "other",
])

// These weights are presentation-only. Operational priority remains owned by the API.
const PRESENTATION_INTENSITY_WEIGHTS: Readonly<Record<OperationalPriorityLevel, number>> =
  Object.freeze({
    critical: 4,
    high: 3,
    medium: 2,
    low: 1,
  })

interface CellAggregate {
  readonly latitude: number
  readonly longitude: number
  readonly categoryTotals: Map<IncidentCategory, number>
}

function quantizeCoordinate(coordinate: number): number {
  const quantized = Number(
    (Math.floor(coordinate / HEATMAP_CELL_SIZE_DEGREES) * HEATMAP_CELL_SIZE_DEGREES).toFixed(3),
  )
  return Object.is(quantized, -0) ? 0 : quantized
}

function cellKey(latitude: number, longitude: number): string {
  return `${latitude.toFixed(3)}:${longitude.toFixed(3)}`
}

function uniqueCategories(categories: readonly IncidentCategory[]): readonly IncidentCategory[] {
  return [...new Set(categories)]
}

function isEligibleIncident(incident: IncidentSummary): boolean {
  if (incident.status === "conflict" || incident.priority === null) {
    return false
  }

  // Pending-review-only evidence has no confirmed reports and must not enter heat aggregation.
  return (
    Number.isFinite(incident.confirmedReportCount) &&
    incident.confirmedReportCount > 0 &&
    Number.isFinite(incident.centroid.latitude) &&
    Number.isFinite(incident.centroid.longitude)
  )
}

function contributionFor(incident: IncidentSummary): number {
  const priorityWeight = PRESENTATION_INTENSITY_WEIGHTS[incident.priority?.level ?? "low"]
  const contribution = incident.confirmedReportCount * priorityWeight
  return Number.isFinite(contribution) && contribution > 0 ? contribution : 0
}

function roundIntensity(value: number): number {
  return Number(value.toFixed(6))
}

/**
 * Builds one deterministic density cell per quantized coordinate.
 *
 * Category dominance is decided here, before any renderer sees the data. This keeps All-mode
 * output independent of API order, object iteration order, viewport size, and MapLibre layer
 * ordering. Pending candidates and incidents without an operational priority are excluded.
 */
export function buildHeatCells(
  incidents: readonly IncidentSummary[],
  mode: HeatmapMode,
): readonly HeatCell[] {
  const aggregates = new Map<string, CellAggregate>()

  for (const incident of incidents) {
    if (!isEligibleIncident(incident)) {
      continue
    }

    const categories = uniqueCategories(incident.categories)
    const selectedCategories =
      mode.kind === "category"
        ? categories.filter((category) => category === mode.category)
        : categories
    if (selectedCategories.length === 0) {
      continue
    }

    const latitude = quantizeCoordinate(incident.centroid.latitude)
    const longitude = quantizeCoordinate(incident.centroid.longitude)
    const key = cellKey(latitude, longitude)
    const existing = aggregates.get(key)
    const aggregate =
      existing ??
      {
        latitude,
        longitude,
        categoryTotals: new Map<IncidentCategory, number>(),
      }
    const contribution = contributionFor(incident)
    if (contribution <= 0) {
      continue
    }

    for (const category of selectedCategories) {
      aggregate.categoryTotals.set(
        category,
        (aggregate.categoryTotals.get(category) ?? 0) + contribution,
      )
    }
    aggregates.set(key, aggregate)
  }

  const unnormalized = [...aggregates.values()]
    .map((aggregate) => {
      let dominantCategory: IncidentCategory
      let dominantTotal: number

      if (mode.kind === "category") {
        dominantCategory = mode.category
        dominantTotal = aggregate.categoryTotals.get(mode.category) ?? 0
      } else {
        dominantCategory = HEATMAP_CATEGORY_ORDER[0]
        dominantTotal = aggregate.categoryTotals.get(dominantCategory) ?? 0
        for (const category of HEATMAP_CATEGORY_ORDER.slice(1)) {
          const total = aggregate.categoryTotals.get(category) ?? 0
          // Deliberately use a strict comparison: the frozen order wins ties.
          if (total > dominantTotal) {
            dominantCategory = category
            dominantTotal = total
          }
        }
      }

      return {
        latitude: aggregate.latitude,
        longitude: aggregate.longitude,
        dominantCategory,
        dominantTotal,
      }
    })
    .filter((cell) => cell.dominantTotal > 0 && Number.isFinite(cell.dominantTotal))

  const maximumTotal = unnormalized.reduce(
    (maximum, cell) => Math.max(maximum, cell.dominantTotal),
    0,
  )
  if (!Number.isFinite(maximumTotal) || maximumTotal <= 0) {
    return []
  }

  const categoryOrderIndex = new Map(
    HEATMAP_CATEGORY_ORDER.map((category, index) => [category, index]),
  )

  return unnormalized
    .map((cell) => ({
      latitude: cell.latitude,
      longitude: cell.longitude,
      intensity: roundIntensity(cell.dominantTotal / maximumTotal),
      dominantCategory: cell.dominantCategory,
    }))
    .sort(
      (left, right) =>
        left.latitude - right.latitude ||
        left.longitude - right.longitude ||
        (categoryOrderIndex.get(left.dominantCategory) ?? Number.MAX_SAFE_INTEGER) -
          (categoryOrderIndex.get(right.dominantCategory) ?? Number.MAX_SAFE_INTEGER),
    )
}

