import { flushPromises, mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import type { IncidentDetailResult } from "../application/incident-detail-port"
import { incidentDetailFixture } from "../testing/incident-fixtures"
import IncidentDetailPage from "./IncidentDetailPage.vue"

class ControllableDetailLoader {
  readonly requests: Array<{ resolve: (result: IncidentDetailResult) => void }> = []

  execute(incidentId: string, signal: AbortSignal): Promise<IncidentDetailResult> {
    void incidentId
    void signal
    return new Promise((resolve) => this.requests.push({ resolve }))
  }
}

describe("IncidentDetailPage", () => {
  it("renders bounded evidence for a current snapshot", async () => {
    const loader = new ControllableDetailLoader()
    const wrapper = mount(IncidentDetailPage, {
      props: { snapshotId: incidentDetailFixture.incidentId, loadIncidentDetail: loader },
    })

    expect(loader.requests).toHaveLength(1)
    loader.requests[0]?.resolve({ ok: true, detail: incidentDetailFixture })
    await flushPromises()

    expect(wrapper.get("h1").text()).toContain("Full incident")
    expect(wrapper.text()).toContain("Street light is out near the community hall")
    expect(wrapper.text()).toContain("More confirmed reports are available")
    expect(wrapper.get("[data-back-to-queue]").text()).toContain("Back to incident queue")
  })

  it("returns an unambiguous missing snapshot to the queue", async () => {
    const loader = new ControllableDetailLoader()
    const wrapper = mount(IncidentDetailPage, {
      props: { snapshotId: incidentDetailFixture.incidentId, loadIncidentDetail: loader },
    })

    expect(loader.requests).toHaveLength(1)
    loader.requests[0]?.resolve({ ok: false, error: { kind: "missing" } })
    await flushPromises()

    expect(wrapper.emitted("stale")).toEqual([[incidentDetailFixture.incidentId]])
  })
})
