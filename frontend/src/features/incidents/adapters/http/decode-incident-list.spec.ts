import { describe, expect, it } from "vitest"

import {
  incidentPageFixture,
  validIncidentListTransportFixture,
} from "../../testing/incident-fixtures"
import { decodeIncidentList } from "./decode-incident-list"

const firstTransportIncident = validIncidentListTransportFixture.items[0]

describe("decodeIncidentList", () => {
  it("maps transport field names while preserving item and category order", () => {
    expect(decodeIncidentList(validIncidentListTransportFixture)).toEqual(incidentPageFixture)
    expect(decodeIncidentList(validIncidentListTransportFixture).items.map(({ incidentId }) => incidentId)).toEqual([
      "ffffffff-ffff-4fff-8fff-ffffffffffff",
      "00000000-0000-4000-8000-000000000000",
    ])
    expect(decodeIncidentList(validIncidentListTransportFixture).items[0]?.categories).toEqual([
      "street_light",
      "blocked_drain",
    ])
  })

  it("preserves a null operational priority", () => {
    expect(decodeIncidentList(validIncidentListTransportFixture).items[1]?.priority).toBeNull()
  })

  it.each(["critical", "high", "medium", "low"] as const)(
    "accepts the %s operational priority level",
    (level) => {
      const value = {
        ...validIncidentListTransportFixture,
        items: [
          {
            ...firstTransportIncident,
            priority: { ...firstTransportIncident.priority, level },
          },
        ],
        total: 1,
      }

      expect(decodeIncidentList(value).items[0]?.priority?.level).toBe(level)
    },
  )

  it("rejects review_required as an incident-summary priority", () => {
    const value = {
      ...validIncidentListTransportFixture,
      items: [
        {
          ...firstTransportIncident,
          priority: { ...firstTransportIncident.priority, level: "review_required" },
        },
      ],
      total: 1,
    }

    expect(() => decodeIncidentList(value)).toThrow(TypeError)
  })

  it("rejects a missing incident field", () => {
    const incident = { ...firstTransportIncident } as Record<string, unknown>
    delete incident.latest_reported_at

    expect(() =>
      decodeIncidentList({ ...validIncidentListTransportFixture, items: [incident], total: 1 }),
    ).toThrow(TypeError)
  })

  it.each([
    { ...validIncidentListTransportFixture, unexpected: true },
    {
      ...validIncidentListTransportFixture,
      items: [{ ...firstTransportIncident, unexpected: true }],
      total: 1,
    },
    {
      ...validIncidentListTransportFixture,
      items: [
        {
          ...firstTransportIncident,
          centroid: { ...firstTransportIncident.centroid, unexpected: true },
        },
      ],
      total: 1,
    },
    {
      ...validIncidentListTransportFixture,
      items: [
        {
          ...firstTransportIncident,
          priority: { ...firstTransportIncident.priority, unexpected: true },
        },
      ],
      total: 1,
    },
  ])("rejects extra object fields", (value) => {
    expect(() => decodeIncidentList(value)).toThrow(TypeError)
  })

  it("rejects an invalid incident UUID", () => {
    const value = {
      ...validIncidentListTransportFixture,
      items: [{ ...firstTransportIncident, incident_id: "not-a-uuid" }],
      total: 1,
    }

    expect(() => decodeIncidentList(value)).toThrow(TypeError)
  })

  it.each(["earliest_reported_at", "latest_reported_at"] as const)(
    "rejects an invalid %s date-time",
    (field) => {
      const value = {
        ...validIncidentListTransportFixture,
        items: [{ ...firstTransportIncident, [field]: "16 July 2026" }],
        total: 1,
      }

      expect(() => decodeIncidentList(value)).toThrow(TypeError)
    },
  )

  it.each([
    {
      ...firstTransportIncident,
      centroid: { ...firstTransportIncident.centroid, latitude: Number.NaN },
    },
    {
      ...firstTransportIncident,
      centroid: { ...firstTransportIncident.centroid, longitude: Number.POSITIVE_INFINITY },
    },
    { ...firstTransportIncident, radius_metres: Number.NEGATIVE_INFINITY },
  ])("rejects non-finite coordinates and radius", (incident) => {
    expect(() =>
      decodeIncidentList({ ...validIncidentListTransportFixture, items: [incident], total: 1 }),
    ).toThrow(TypeError)
  })

  it.each([
    null,
    [],
    { ...validIncidentListTransportFixture, items: {} },
    { ...validIncidentListTransportFixture, limit: "100" },
    { ...validIncidentListTransportFixture, offset: Number.NaN },
    { ...validIncidentListTransportFixture, total: Number.POSITIVE_INFINITY },
  ])("rejects a malformed page envelope", (value) => {
    expect(() => decodeIncidentList(value)).toThrow(TypeError)
  })
})
