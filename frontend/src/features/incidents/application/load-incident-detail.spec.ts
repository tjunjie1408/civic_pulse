import { describe, expect, it } from "vitest"

import type { IncidentDetailPort, IncidentDetailResult } from "./incident-detail-port"
import { LoadIncidentDetail } from "./load-incident-detail"

describe("LoadIncidentDetail", () => {
  it("delegates the snapshot ID and abort signal to the detail port", async () => {
    const result: IncidentDetailResult = { ok: false, error: { kind: "missing" } }
    const port: IncidentDetailPort = {
      get: (incidentId, signal) => {
        expect(incidentId).toBe("snapshot-1")
        expect(signal.aborted).toBe(false)
        return Promise.resolve(result)
      },
    }
    const loader = new LoadIncidentDetail(port)
    const signal = new AbortController().signal

    await expect(loader.execute("snapshot-1", signal)).resolves.toBe(result)
  })
})
