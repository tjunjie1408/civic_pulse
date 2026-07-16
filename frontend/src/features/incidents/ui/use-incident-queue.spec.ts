import { effectScope, isReadonly } from "vue"
import { describe, expect, it } from "vitest"

import type { IncidentListResult } from "../application/incident-list-port"
import type { IncidentPage, IncidentSummary } from "../domain/incident"
import { incidentPageFixture } from "../testing/incident-fixtures"
import { useIncidentQueue } from "./use-incident-queue"

interface PendingRequest {
  readonly signal: AbortSignal
  readonly resolve: (result: IncidentListResult) => void
}

class ControllableLoadIncidentQueue {
  readonly requests: PendingRequest[] = []

  execute(signal: AbortSignal): Promise<IncidentListResult> {
    return new Promise((resolve) => {
      this.requests.push({ signal, resolve })
    })
  }

  resolve(index: number, result: IncidentListResult): void {
    const request = this.requests[index]
    if (request === undefined) {
      throw new Error(`No request exists at index ${index}`)
    }
    request.resolve(result)
  }
}

function incidentPage(...incidentIds: readonly string[]): IncidentPage {
  const template = incidentPageFixture.items[0]
  if (template === undefined) {
    throw new Error("The incident fixture must contain a template incident")
  }

  const items: IncidentSummary[] = incidentIds.map((incidentId) => ({
    ...template,
    incidentId,
  }))
  return {
    items,
    limit: 100,
    offset: 0,
    total: items.length,
  }
}

function createQueue() {
  const loadIncidentQueue = new ControllableLoadIncidentQueue()
  const scope = effectScope()
  const queue = scope.run(() => useIncidentQueue(loadIncidentQueue))
  if (queue === undefined) {
    throw new Error("The queue composable must be created inside its effect scope")
  }
  return { loadIncidentQueue, queue, scope }
}

describe("useIncidentQueue", () => {
  it("moves an initial load from loading to ready without changing API order", async () => {
    const { loadIncidentQueue, queue, scope } = createQueue()
    const page = incidentPage("incident-b", "incident-a")

    expect(isReadonly(queue.state)).toBe(true)
    expect(queue.state.value).toEqual({ kind: "loading", previous: null })

    const load = queue.load()
    expect(queue.state.value).toEqual({ kind: "loading", previous: null })

    loadIncidentQueue.resolve(0, { ok: true, page })
    await load

    expect(queue.state.value).toEqual({ kind: "ready", page })
    expect(
      queue.state.value.kind === "ready"
        ? queue.state.value.page.items.map(({ incidentId }) => incidentId)
        : [],
    ).toEqual(["incident-b", "incident-a"])
    scope.stop()
  })

  it("models a successful page with no incidents as empty", async () => {
    const { loadIncidentQueue, queue, scope } = createQueue()
    const page = incidentPage()

    const load = queue.load()
    loadIncidentQueue.resolve(0, { ok: true, page })
    await load

    expect(queue.state.value).toEqual({ kind: "empty", page })
    scope.stop()
  })

  it("models an initial recoverable error as failed without a previous page", async () => {
    const { loadIncidentQueue, queue, scope } = createQueue()

    const load = queue.load()
    loadIncidentQueue.resolve(0, { ok: false, error: { kind: "network" } })
    await load

    expect(queue.state.value).toEqual({
      kind: "failed",
      previous: null,
      error: { kind: "network" },
    })
    scope.stop()
  })

  it("retains the ready page while refresh loads and after refresh fails", async () => {
    const { loadIncidentQueue, queue, scope } = createQueue()
    const page = incidentPage("incident-a")
    const initialLoad = queue.load()
    loadIncidentQueue.resolve(0, { ok: true, page })
    await initialLoad

    const refresh = queue.refresh()
    expect(queue.state.value).toEqual({ kind: "loading", previous: page })

    loadIncidentQueue.resolve(1, {
      ok: false,
      error: { kind: "service", status: 503 },
    })
    await refresh

    expect(queue.state.value).toEqual({
      kind: "failed",
      previous: page,
      error: { kind: "service", status: 503 },
    })
    scope.stop()
  })

  it("retries a failure and replaces the previous page in exact API order", async () => {
    const { loadIncidentQueue, queue, scope } = createQueue()
    const previous = incidentPage("incident-old")
    const initialLoad = queue.load()
    loadIncidentQueue.resolve(0, { ok: true, page: previous })
    await initialLoad
    const refresh = queue.refresh()
    loadIncidentQueue.resolve(1, { ok: false, error: { kind: "contract" } })
    await refresh
    const replacement = incidentPage("incident-c", "incident-a", "incident-b")

    const retry = queue.retry()
    expect(queue.state.value).toEqual({ kind: "loading", previous })
    loadIncidentQueue.resolve(2, { ok: true, page: replacement })
    await retry

    expect(queue.state.value).toEqual({ kind: "ready", page: replacement })
    expect(
      queue.state.value.kind === "ready"
        ? queue.state.value.page.items.map(({ incidentId }) => incidentId)
        : [],
    ).toEqual(["incident-c", "incident-a", "incident-b"])
    scope.stop()
  })

  it("aborts an older request and ignores its late response", async () => {
    const { loadIncidentQueue, queue, scope } = createQueue()
    const oldLoad = queue.load()
    const newLoad = queue.refresh()

    expect(loadIncidentQueue.requests[0]?.signal.aborted).toBe(true)
    expect(loadIncidentQueue.requests[1]?.signal.aborted).toBe(false)

    const currentPage = incidentPage("incident-current")
    loadIncidentQueue.resolve(1, { ok: true, page: currentPage })
    await newLoad
    const stalePage = incidentPage("incident-stale")
    loadIncidentQueue.resolve(0, { ok: true, page: stalePage })
    await oldLoad

    expect(queue.state.value).toEqual({ kind: "ready", page: currentPage })
    scope.stop()
  })

  it("aborts the active request on scope disposal without exposing an aborted failure", async () => {
    const { loadIncidentQueue, queue, scope } = createQueue()
    const load = queue.load()

    scope.stop()
    expect(loadIncidentQueue.requests[0]?.signal.aborted).toBe(true)
    loadIncidentQueue.resolve(0, { ok: false, error: { kind: "aborted" } })
    await load

    expect(queue.state.value).toEqual({ kind: "loading", previous: null })
    expect(queue.state.value.kind).not.toBe("failed")
  })
})
