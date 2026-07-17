import { describe, expect, it } from "vitest"

import type { IncidentPage, IncidentSummary } from "../domain/incident"
import type {
  IncidentListPort,
  IncidentListQuery,
  IncidentListResult,
} from "./incident-list-port"
import { LoadIncidentQueue } from "./load-incident-queue"

interface IncidentListCall {
  readonly query: IncidentListQuery
  readonly signal: AbortSignal
}

class RecordingIncidentListPort implements IncidentListPort {
  readonly calls: IncidentListCall[] = []

  constructor(private readonly result: IncidentListResult) {}

  list(query: IncidentListQuery, signal: AbortSignal): Promise<IncidentListResult> {
    this.calls.push({ query, signal })
    return Promise.resolve(this.result)
  }
}

function incidentSummary(incidentId: string): IncidentSummary {
  return {
    incidentId,
    status: "confirmed",
    categories: ["other"],
    priority: { level: "low", reasons: [], policyVersion: "test" },
    confirmedReportCount: 1,
    pendingCandidateCount: 0,
    centroid: { latitude: 1.3, longitude: 103.8 },
    radiusMetres: 50,
    earliestReportedAt: "2026-07-16T01:00:00Z",
    latestReportedAt: "2026-07-16T02:00:00Z",
    conflictReasons: [],
  }
}

const incidentPageFixture = {
  items: [incidentSummary("incident-b"), incidentSummary("incident-a")],
  limit: 100,
  offset: 0,
  total: 2,
} as const satisfies IncidentPage

describe("LoadIncidentQueue", () => {
  it("delegates the initial page request and preserves the port result order", async () => {
    const portResult = { ok: true, page: incidentPageFixture } as const satisfies IncidentListResult
    const port = new RecordingIncidentListPort(portResult)
    const signal = new AbortController().signal
    const loadIncidentQueue = new LoadIncidentQueue(port)

    const result = await loadIncidentQueue.execute(signal)

    expect(port.calls).toHaveLength(1)
    expect(port.calls[0]).toEqual({ query: { limit: 100, offset: 0 }, signal })
    expect(port.calls[0]?.signal).toBe(signal)
    expect(result).toBe(portResult)
    expect(result.ok && result.page.items).toBe(incidentPageFixture.items)
  })
})
