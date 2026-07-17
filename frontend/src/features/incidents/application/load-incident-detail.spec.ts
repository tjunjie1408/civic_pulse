import { describe, expect, it } from "vitest"

import type { IncidentDetail } from "../domain/incident"
import type {
  IncidentDetailError,
  IncidentDetailPort,
  IncidentDetailResult,
} from "./incident-detail-port"
import { LoadIncidentDetail } from "./load-incident-detail"

const detail: IncidentDetail = {
  incidentId: "ffffffff-ffff-4fff-8fff-ffffffffffff",
  status: "confirmed",
  categories: ["flooding"],
  priority: null,
  confirmedReportCount: 1,
  pendingCandidateCount: 0,
  centroid: { latitude: 3.08, longitude: 101.52 },
  radiusMetres: 50,
  earliestReportedAt: "2026-07-16T01:00:00Z",
  latestReportedAt: "2026-07-16T02:00:00Z",
  conflictReasons: [],
  complaintIds: [],
  reviewCandidateIds: [],
  confirmedEdges: [],
  reviewCandidates: [],
}

class RecordingPort implements IncidentDetailPort {
  readonly calls: Array<{ incidentId: string; signal: AbortSignal }> = []

  constructor(private readonly result: IncidentDetailResult) {}

  get(incidentId: string, signal: AbortSignal): Promise<IncidentDetailResult> {
    this.calls.push({ incidentId, signal })
    return Promise.resolve(this.result)
  }
}

describe("LoadIncidentDetail", () => {
  it("delegates the exact snapshot ID and signal without reshaping the result", async () => {
    const result = { ok: true, detail } as const satisfies IncidentDetailResult
    const port = new RecordingPort(result)
    const signal = new AbortController().signal

    const loaded = await new LoadIncidentDetail(port).execute(detail.incidentId, signal)

    expect(port.calls).toEqual([{ incidentId: detail.incidentId, signal }])
    expect(port.calls[0]?.signal).toBe(signal)
    expect(loaded).toBe(result)
  })

  it("preserves missing, service, contract, network, and aborted outcomes", async () => {
    const errors = [
      { kind: "missing" },
      { kind: "service", status: 503 },
      { kind: "contract" },
      { kind: "network" },
      { kind: "aborted" },
    ] as const satisfies readonly IncidentDetailError[]

    for (const error of errors) {
      const result = { ok: false, error } as const satisfies IncidentDetailResult
      const loaded = await new LoadIncidentDetail(new RecordingPort(result)).execute(
        detail.incidentId,
        new AbortController().signal,
      )
      expect(loaded).toBe(result)
    }
  })
})
