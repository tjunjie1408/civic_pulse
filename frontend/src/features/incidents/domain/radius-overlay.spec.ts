import { describe, expect, it } from "vitest"

import { projectAffectedAreas } from "./radius-overlay"

const incident = {
  incidentId: "incident-1",
  centroid: { latitude: 1.3, longitude: 103.8 },
  radiusMetres: 100,
}

describe("projectAffectedAreas", () => {
  it("projects zero-radius incidents as a centroid point", () => {
    const result = projectAffectedAreas([{ ...incident, radiusMetres: 0 }])

    expect(result.features).toEqual([
      {
        type: "Feature",
        properties: { incidentId: "incident-1", radiusMetres: 0 },
        geometry: { type: "Point", coordinates: [103.8, 1.3] },
      },
    ])
  })

  it("projects a positive radius as a closed geodesic polygon", () => {
    const result = projectAffectedAreas([incident])
    const feature = result.features[0]

    expect(feature?.geometry.type).toBe("Polygon")
    if (feature?.geometry.type !== "Polygon") {
      return
    }

    const ring = feature.geometry.coordinates[0]
    expect(ring).toHaveLength(65)
    expect(ring[0]).toEqual(ring[ring.length - 1])
    expect(feature.properties.radiusMetres).toBe(100)
  })

  it("uses metre-scale north and east offsets", () => {
    const result = projectAffectedAreas([incident])
    const feature = result.features[0]

    if (feature?.geometry.type !== "Polygon") {
      throw new Error("Expected a polygon")
    }

    const ring = feature.geometry.coordinates[0]
    const north = ring[0]
    const east = ring[16]
    expect(north?.[1]).toBeCloseTo(1.300899, 5)
    expect(east?.[0]).toBeCloseTo(103.800900, 5)
  })

  it("excludes incidents with non-finite coordinates or radius", () => {
    const result = projectAffectedAreas([
      incident,
      { ...incident, incidentId: "nan-coordinate", centroid: { latitude: Number.NaN, longitude: 1 } },
      { ...incident, incidentId: "infinite-radius", radiusMetres: Number.POSITIVE_INFINITY },
    ])

    expect(result.features.map((feature) => feature.properties.incidentId)).toEqual(["incident-1"])
  })
})
