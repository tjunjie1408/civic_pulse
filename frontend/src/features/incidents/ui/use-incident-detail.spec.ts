import { effectScope } from "vue"
import { describe, expect, it } from "vitest"

import type { IncidentDetailResult } from "../application/incident-detail-port"
import type { IncidentDetail } from "../domain/incident"
import { incidentDetailFixture } from "../testing/incident-fixtures"
import { useIncidentDetail } from "./use-incident-detail"

interface PendingRequest {
  readonly incidentId: string
  readonly signal: AbortSignal
  readonly resolve: (result: IncidentDetailResult) => void
}

class ControllableLoadIncidentDetail {
  readonly requests: PendingRequest[] = []

  execute(incidentId: string, signal: AbortSignal): Promise<IncidentDetailResult> {
    return new Promise((resolve) => this.requests.push({ incidentId, signal, resolve }))
  }
}

function createDetail() {
  const loader = new ControllableLoadIncidentDetail()
  const scope = effectScope()
  const detail = scope.run(() => useIncidentDetail(loader))
  if (detail === undefined) throw new Error("The detail composable must be scoped")
  return { loader, detail, scope }
}

describe("useIncidentDetail", () => {
  it("loads one snapshot into a readonly ready state", async () => {
    const { loader, detail, scope } = createDetail()
    const request = detail.load(incidentDetailFixture.incidentId)
    loader.requests[0]?.resolve({ ok: true, detail: incidentDetailFixture as unknown as IncidentDetail })
    await request

    expect(detail.state.value).toEqual({
      kind: "ready",
      incidentId: incidentDetailFixture.incidentId,
      detail: incidentDetailFixture,
    })
    scope.stop()
  })

  it("keeps a missing snapshot explicit", async () => {
    const { loader, detail, scope } = createDetail()
    const request = detail.load("missing-snapshot")
    loader.requests[0]?.resolve({ ok: false, error: { kind: "missing" } })
    await request

    expect(detail.state.value).toEqual({ kind: "missing", incidentId: "missing-snapshot" })
    scope.stop()
  })

  it("aborts older loads and ignores their late response", async () => {
    const { loader, detail, scope } = createDetail()
    const oldRequest = detail.load("old")
    const currentRequest = detail.load(incidentDetailFixture.incidentId)

    expect(loader.requests[0]?.signal.aborted).toBe(true)
    loader.requests[1]?.resolve({ ok: true, detail: incidentDetailFixture as unknown as IncidentDetail })
    await currentRequest
    loader.requests[0]?.resolve({ ok: false, error: { kind: "missing" } })
    await oldRequest

    expect(detail.state.value.kind).toBe("ready")
    expect(detail.state.value.kind === "ready" ? detail.state.value.incidentId : null).toBe(
      incidentDetailFixture.incidentId,
    )
    scope.stop()
  })
})
