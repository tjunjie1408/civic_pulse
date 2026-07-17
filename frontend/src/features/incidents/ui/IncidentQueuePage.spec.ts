import { flushPromises, mount } from "@vue/test-utils"
import { describe, expect, it, vi } from "vitest"

import type { IncidentMapRenderer, MapRenderStrategy } from "../application/incident-map-port"
import type { IncidentListResult } from "../application/incident-list-port"
import type { HeatCell, HeatmapMode } from "../domain/heatmap"
import type { IncidentPage } from "../domain/incident"
import { incidentPageFixture } from "../testing/incident-fixtures"
import IncidentQueuePage from "./IncidentQueuePage.vue"

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

function page(overrides: Partial<IncidentPage> = {}): IncidentPage {
  return { ...incidentPageFixture, ...overrides }
}

describe("IncidentQueuePage", () => {
  it("renders the map panel beside the API-ordered queue", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const mountSpy = vi.fn()
    const renderSpy = vi.fn(
      (_cells: readonly HeatCell[], mode: HeatmapMode): MapRenderStrategy =>
        mode.kind === "all" ? "neutral-density" : "category-heat",
    )
    const renderer: IncidentMapRenderer = {
      mount: mountSpy,
      render: renderSpy,
      resize: vi.fn(),
      dispose: vi.fn(),
    }
    const wrapper = mount(IncidentQueuePage, {
      props: {
        loadIncidentQueue: loader,
        createIncidentMapRenderer: () => renderer,
      },
    })
    loader.resolve(0, { ok: true, page: page() })
    await flushPromises()

    expect(wrapper.findComponent({ name: "IncidentMapPanel" }).exists()).toBe(true)
    expect(wrapper.findAll("ol > li h2").map((heading) => heading.text())).toEqual([
      "Street light · Blocked drain",
      "Other · Flooding",
    ])
    expect(mountSpy).toHaveBeenCalledOnce()
  })

  it("shows an aria-busy loading state without a false empty message", () => {
    const loader = new ControllableLoadIncidentQueue()
    const wrapper = mount(IncidentQueuePage, { props: { loadIncidentQueue: loader } })

    expect(wrapper.get("section").attributes("aria-busy")).toBe("true")
    expect(wrapper.get('[role="status"]').text()).toContain("Loading incidents")
    expect(wrapper.text()).not.toContain("No active incidents")
  })

  it("renders a clear empty success state", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const wrapper = mount(IncidentQueuePage, { props: { loadIncidentQueue: loader } })
    loader.resolve(0, { ok: true, page: page({ items: [], total: 0 }) })
    await flushPromises()

    expect(wrapper.get("section").attributes("aria-busy")).toBe("false")
    expect(wrapper.get('[role="status"]').text()).toContain("No active incidents")
    expect(wrapper.find("ol").exists()).toBe(false)
  })

  it("shows one retry action after an initial failure", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const wrapper = mount(IncidentQueuePage, { props: { loadIncidentQueue: loader } })
    loader.resolve(0, { ok: false, error: { kind: "network" } })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain("Unable to load incidents")
    expect(wrapper.findAll("button").map((button) => button.text())).toEqual(["Retry"])
  })

  it("renders ready incidents in the exact API order", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const orderedPage = page({
      items: [incidentPageFixture.items[1], incidentPageFixture.items[0]],
      total: 2,
    })
    const wrapper = mount(IncidentQueuePage, { props: { loadIncidentQueue: loader } })
    loader.resolve(0, { ok: true, page: orderedPage })
    await flushPromises()

    expect(wrapper.findAll("ol > li h2").map((heading) => heading.text())).toEqual([
      "Other · Flooding",
      "Street light · Blocked drain",
    ])
  })

  it("keeps stale rows visible under a refresh-failure notice", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const wrapper = mount(IncidentQueuePage, { props: { loadIncidentQueue: loader } })
    loader.resolve(0, { ok: true, page: page({ items: [incidentPageFixture.items[0]], total: 1 }) })
    await flushPromises()

    await wrapper.get('button[aria-label="Refresh incidents"]').trigger("click")
    loader.resolve(1, { ok: false, error: { kind: "service", status: 503 } })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain("Showing last known incidents")
    expect(wrapper.findAll("ol > li")).toHaveLength(1)
    expect(wrapper.findAll("button").map((button) => button.text())).toContain("Retry")
  })

  it("starts exactly one request for a single retry action", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const wrapper = mount(IncidentQueuePage, { props: { loadIncidentQueue: loader } })
    loader.resolve(0, { ok: false, error: { kind: "contract" } })
    await flushPromises()

    await wrapper.get("button").trigger("click")
    expect(loader.requests).toHaveLength(2)
    loader.resolve(1, { ok: true, page: page() })
    await flushPromises()
    expect(wrapper.findAll("ol > li")).toHaveLength(2)
  })

  it("reports the total when more incidents exist without pagination controls", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const wrapper = mount(IncidentQueuePage, { props: { loadIncidentQueue: loader } })
    const visibleItems = Array.from({ length: 100 }, (_, index) => ({
      ...incidentPageFixture.items[index % incidentPageFixture.items.length],
      incidentId: `incident-${index}`,
    }))
    loader.resolve(0, { ok: true, page: page({ items: visibleItems, total: 125 }) })
    await flushPromises()

    expect(wrapper.text()).toContain("Showing 100 of 125")
    expect(wrapper.text()).not.toContain("Next page")
    expect(wrapper.text()).not.toContain("Previous page")
  })
})
