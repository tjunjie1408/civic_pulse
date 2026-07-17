import { describe, expect, it } from "vitest"

import {
  incidentDetailFixture,
  validIncidentDetailTransportFixture,
} from "../../testing/incident-fixtures"
import { decodeIncidentDetail } from "./decode-incident-detail"

describe("decodeIncidentDetail", () => {
  it("maps bounded confirmed report summaries and preserves has_more", () => {
    expect(decodeIncidentDetail(validIncidentDetailTransportFixture)).toEqual(incidentDetailFixture)
  })

  it.each([
    { ...validIncidentDetailTransportFixture, photo_path: "C:\\private\\photo.jpg" },
    {
      ...validIncidentDetailTransportFixture,
      confirmed_reports: {
        ...validIncidentDetailTransportFixture.confirmed_reports,
        items: [{ ...validIncidentDetailTransportFixture.confirmed_reports.items[0], photo_path: "x" }],
      },
    },
  ])("rejects filesystem-path fields", (value) => {
    expect(() => decodeIncidentDetail(value)).toThrow(TypeError)
  })

  it("rejects an unbounded preview envelope", () => {
    const value = {
      ...validIncidentDetailTransportFixture,
      confirmed_reports: {
        ...validIncidentDetailTransportFixture.confirmed_reports,
        has_more: "yes",
      },
    }
    expect(() => decodeIncidentDetail(value)).toThrow(TypeError)
  })

  it("rejects an extra field on the detail envelope", () => {
    expect(() => decodeIncidentDetail({ ...validIncidentDetailTransportFixture, unexpected: true })).toThrow(
      TypeError,
    )
  })
})
