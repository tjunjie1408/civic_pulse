import { flushPromises, mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import type { IncidentListResult } from "./features/incidents/application/incident-list-port"
import { incidentPageFixture } from "./features/incidents/testing/incident-fixtures"
import App from "./App.vue"

class FakeLoadIncidentQueue {
  execute(signal: AbortSignal): Promise<IncidentListResult> {
    void signal
    return Promise.resolve({ ok: true, page: incidentPageFixture })
  }
}

describe("App shell", () => {
  it("provides the CivicPulse incident operations landmarks", async () => {
    const wrapper = mount(App, {
      props: { loadIncidentQueue: new FakeLoadIncidentQueue() },
    })
    const banner = wrapper.find("header")

    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain("CivicPulse")
    expect(wrapper.get("h1").text()).toBe("Incident operations")
    expect(wrapper.find("main").exists()).toBe(true)
    await flushPromises()
    expect(wrapper.get(".incident-queue").text()).toContain("Active incident queue")
    expect(wrapper.findAll(".incident-queue-row")).toHaveLength(2)
  })
})
