import { describe, expect, it } from "vitest"

import {
  incidentDetailFixture,
  validIncidentDetailTransportFixture,
} from "../../testing/incident-fixtures"
import { decodeIncidentDetail } from "./decode-incident-detail"

type ComplaintPayload = {
  complaint_id: string
  text: string
  category: string
  latitude: number
  longitude: number
  reported_at: string
  photo_available: boolean
  photo_url: string | null
  [key: string]: unknown
}

type DetailPayload = Omit<typeof validIncidentDetailTransportFixture, "confirmed_reports"> & {
  confirmed_reports: {
    items: ComplaintPayload[]
    total: number
    has_more: boolean
  }
  [key: string]: unknown
}

function buildValidDetailPayload(): DetailPayload {
  return {
    ...validIncidentDetailTransportFixture,
    confirmed_reports: {
      ...validIncidentDetailTransportFixture.confirmed_reports,
      items: validIncidentDetailTransportFixture.confirmed_reports.items.map(
        (item): ComplaintPayload => ({
          ...item,
          photo_url: null,
        }),
      ),
    },
  }
}

function buildExpectedIncidentDetail() {
  return {
    ...incidentDetailFixture,
    confirmedReports: {
      ...incidentDetailFixture.confirmedReports,
      items: incidentDetailFixture.confirmedReports.items.map((item) => ({
        ...item,
        photoUrl: null,
      })),
    },
  }
}

describe("decodeIncidentDetail", () => {
  it("maps bounded confirmed report summaries and preserves has_more", () => {
    expect(decodeIncidentDetail(buildValidDetailPayload())).toEqual(buildExpectedIncidentDetail())
  })

  it.each([
    {
      ...buildValidDetailPayload(),
      photo_path: "C:\\private\\photo.jpg",
    },
    {
      ...buildValidDetailPayload(),
      confirmed_reports: {
        ...buildValidDetailPayload().confirmed_reports,
        items: [{ ...buildValidDetailPayload().confirmed_reports.items[0], photo_path: "x" }],
      },
    },
  ])("rejects filesystem-path fields", (value) => {
    expect(() => decodeIncidentDetail(value)).toThrow(TypeError)
  })

  it("rejects an unbounded preview envelope", () => {
    const value = {
      ...buildValidDetailPayload(),
      confirmed_reports: {
        ...buildValidDetailPayload().confirmed_reports,
        has_more: "yes",
      },
    }
    expect(() => decodeIncidentDetail(value)).toThrow(TypeError)
  })

  it("rejects an extra field on the detail envelope", () => {
    expect(() => decodeIncidentDetail({ ...buildValidDetailPayload(), unexpected: true })).toThrow(
      TypeError,
    )
  })

  it("decodes photo_url into photoUrl", () => {
    const payload = buildValidDetailPayload()
    payload.confirmed_reports.items[0].photo_url =
      "/api/v1/photos/30000000-0000-0000-0000-000000000001"

    const detail = decodeIncidentDetail(payload)

    expect(detail.confirmedReports.items[0].photoUrl).toBe(
      "/api/v1/photos/30000000-0000-0000-0000-000000000001",
    )
  })

  it("accepts a null photo_url", () => {
    const payload = buildValidDetailPayload()
    payload.confirmed_reports.items[0].photo_url = null

    expect(decodeIncidentDetail(payload).confirmedReports.items[0].photoUrl).toBeNull()
  })

  it("rejects complaint rows without photo_url", () => {
    const payload = buildValidDetailPayload()
    delete (payload.confirmed_reports.items[0] as Partial<ComplaintPayload>).photo_url

    expect(() => decodeIncidentDetail(payload)).toThrowError(TypeError)
  })

  it("rejects photo_url values outside the photos endpoint", () => {
    const payload = buildValidDetailPayload()
    payload.confirmed_reports.items[0].photo_url = "https://evil.example/x.jpg"

    expect(() => decodeIncidentDetail(payload)).toThrowError(TypeError)
  })
})
