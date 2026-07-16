import { describe, expect, it } from "vitest"

import type { IncidentCategory, IncidentSummary, OperationalPriorityLevel } from "./incident"
import {
  HEATMAP_CATEGORY_ORDER,
  buildHeatCells,
  type HeatmapMode,
} from "./heatmap"

function incident(
  overrides: Partial<IncidentSummary> & Pick<IncidentSummary, "incidentId">,
): IncidentSummary {
  const { incidentId, ...remainingOverrides } = overrides
  return {
    incidentId,
    status: "confirmed",
    categories: ["other"],
    priority: { level: "medium", reasons: [], policyVersion: "test" },
    confirmedReportCount: 1,
    pendingCandidateCount: 0,
    centroid: { latitude: 1.3, longitude: 103.8 },
    radiusMetres: 50,
    earliestReportedAt: "2026-07-16T01:00:00Z",
    latestReportedAt: "2026-07-16T02:00:00Z",
    conflictReasons: [],
    ...remainingOverrides,
  }
}

function categoryIncident(
  incidentId: string,
  category: IncidentCategory,
  level: OperationalPriorityLevel,
  confirmedReportCount: number,
  coordinates = { latitude: 1.3, longitude: 103.8 },
): IncidentSummary {
  return incident({
    incidentId,
    categories: [category],
    priority: { level, reasons: [], policyVersion: "test" },
    confirmedReportCount,
    centroid: coordinates,
  })
}

const allMode: HeatmapMode = { kind: "all" }

describe("buildHeatCells", () => {
  it("excludes conflict and no-priority incidents", () => {
    const cells = buildHeatCells(
      [
        categoryIncident("eligible", "flooding", "high", 2),
        incident({
          incidentId: "conflict-status",
          status: "conflict",
          categories: ["rubbish"],
          priority: { level: "critical", reasons: [], policyVersion: "test" },
          confirmedReportCount: 20,
        }),
        incident({
          incidentId: "no-priority",
          categories: ["pothole"],
          priority: null,
          confirmedReportCount: 20,
        }),
      ],
      allMode,
    )

    expect(cells).toEqual([
      {
        latitude: 1.3,
        longitude: 103.8,
        intensity: 1,
        dominantCategory: "flooding",
      },
    ])
  })

  it("excludes pending-review-only evidence from confirmed heat", () => {
    const cells = buildHeatCells(
      [
        categoryIncident("eligible", "flooding", "low", 2),
        incident({
          incidentId: "pending-only",
          categories: ["flooding"],
          priority: { level: "critical", reasons: [], policyVersion: "test" },
          confirmedReportCount: 0,
          pendingCandidateCount: 8,
        }),
      ],
      allMode,
    )

    expect(cells).toEqual([
      {
        latitude: 1.3,
        longitude: 103.8,
        intensity: 1,
        dominantCategory: "flooding",
      },
    ])
  })

  it("uses a stable fixed grid cell for coordinates", () => {
    const cells = buildHeatCells(
      [
        categoryIncident("quantized", "pothole", "low", 1, {
          latitude: 1.2349,
          longitude: 103.8769,
        }),
      ],
      allMode,
    )

    expect(cells).toEqual([
      {
        latitude: 1.234,
        longitude: 103.876,
        intensity: 1,
        dominantCategory: "pothole",
      },
    ])
  })

  it("selects the strongest category in All mode without mixing colors", () => {
    const cells = buildHeatCells(
      [
        categoryIncident("flood", "flooding", "critical", 2),
        categoryIncident("rubbish", "rubbish", "low", 1),
      ],
      allMode,
    )

    expect(cells).toHaveLength(1)
    expect(cells[0]).toMatchObject({ dominantCategory: "flooding", intensity: 1 })
  })

  it("uses the frozen category order when category intensity ties", () => {
    expect(HEATMAP_CATEGORY_ORDER).toEqual([
      "flooding",
      "blocked_drain",
      "pothole",
      "rubbish",
      "street_light",
      "other",
    ])

    const cells = buildHeatCells(
      [
        categoryIncident("drain", "blocked_drain", "low", 1),
        categoryIncident("flood", "flooding", "low", 1),
      ],
      allMode,
    )

    expect(cells).toEqual([
      {
        latitude: 1.3,
        longitude: 103.8,
        intensity: 1,
        dominantCategory: "flooding",
      },
    ])
  })

  it("computes a single-category result independently", () => {
    const incidents = [
      categoryIncident("flood-a", "flooding", "critical", 4),
      categoryIncident("rubbish-a", "rubbish", "low", 1),
      categoryIncident("rubbish-b", "rubbish", "low", 4, {
        latitude: 1.301,
        longitude: 103.801,
      }),
    ]

    expect(buildHeatCells(incidents, allMode)).toEqual([
      {
        latitude: 1.3,
        longitude: 103.8,
        intensity: 1,
        dominantCategory: "flooding",
      },
      {
        latitude: 1.301,
        longitude: 103.801,
        intensity: 0.25,
        dominantCategory: "rubbish",
      },
    ])

    expect(
      buildHeatCells(incidents, { kind: "category", category: "rubbish" }),
    ).toEqual([
      {
        latitude: 1.3,
        longitude: 103.8,
        intensity: 0.25,
        dominantCategory: "rubbish",
      },
      {
        latitude: 1.301,
        longitude: 103.801,
        intensity: 1,
        dominantCategory: "rubbish",
      },
    ])
  })

  it("does not change output when input incidents are permuted", () => {
    const incidents = [
      categoryIncident("a", "street_light", "medium", 2, {
        latitude: 1.302,
        longitude: 103.802,
      }),
      categoryIncident("b", "flooding", "high", 1),
      categoryIncident("c", "street_light", "low", 1),
      categoryIncident("d", "other", "critical", 1, {
        latitude: 1.301,
        longitude: 103.801,
      }),
    ]

    expect(buildHeatCells(incidents, allMode)).toEqual(
      buildHeatCells([...incidents].reverse(), allMode),
    )
  })
})
