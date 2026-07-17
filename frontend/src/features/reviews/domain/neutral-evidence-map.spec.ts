import { describe, expect, it } from "vitest"

import { projectNeutralEvidencePoints } from "./neutral-evidence-map"
import { reviewDetailFixture } from "../testing/review-fixtures"

describe("projectNeutralEvidencePoints", () => {
  it("projects both submitted locations without deriving an incident radius", () => {
    const projection = projectNeutralEvidencePoints(reviewDetailFixture)

    expect(projection.points.map((point) => point.key)).toEqual(["a", "b"])
    expect(projection.points.every((point) => point.x >= 0 && point.x <= 100)).toBe(true)
    expect(projection.points.every((point) => point.y >= 0 && point.y <= 100)).toBe(true)
    expect(projection.points[0]?.latitude).toBe(reviewDetailFixture.complaintA.latitude)
    expect(projection.points[1]?.longitude).toBe(reviewDetailFixture.complaintB.longitude)
  })

  it("keeps identical locations visibly distinct without inventing distance", () => {
    const detail = {
      ...reviewDetailFixture,
      complaintB: {
        ...reviewDetailFixture.complaintB,
        latitude: reviewDetailFixture.complaintA.latitude,
        longitude: reviewDetailFixture.complaintA.longitude,
      },
    }

    const projection = projectNeutralEvidencePoints(detail)

    expect(projection.points[0]?.x).toBe(28)
    expect(projection.points[1]?.x).toBe(72)
    expect(projection.points[0]?.latitude).toBe(projection.points[1]?.latitude)
  })
})
