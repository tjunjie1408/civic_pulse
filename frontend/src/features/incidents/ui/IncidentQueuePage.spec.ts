import { flushPromises, mount } from "@vue/test-utils"
import { describe, expect, it, vi } from "vitest"
import { nextTick } from "vue"

import type {
  IncidentMapRenderer,
  IncidentMapView,
  MapRenderStrategy,
} from "../application/incident-map-port"
import type { IncidentDetailResult } from "../application/incident-detail-port"
import type { IncidentListResult } from "../application/incident-list-port"
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

class ControllableLoadIncidentDetail {
  readonly requests: Array<{
    readonly incidentId: string
    readonly resolve: (result: IncidentDetailResult) => void
  }> = []

  execute(incidentId: string, signal: AbortSignal): Promise<IncidentDetailResult> {
    void signal
    return new Promise((resolve) => this.requests.push({ incidentId, resolve }))
  }
}

function rendererHarness() {
  const selections = new Set<(incidentId: string) => void>()
  const previews = new Set<(incidentId: string | null) => void>()
  const mountSpy = vi.fn()
  const renderSpy = vi.fn((view: IncidentMapView): MapRenderStrategy =>
    view.mode.kind === "all" ? "neutral-density" : "category-heat",
  )
  const renderer: IncidentMapRenderer = {
    mount: mountSpy,
    render: renderSpy,
    resize: vi.fn(),
    onIncidentSelect: (listener) => {
      selections.add(listener)
      return () => selections.delete(listener)
    },
    onIncidentPreview: (listener) => {
      previews.add(listener)
      return () => previews.delete(listener)
    },
    onLifecycleChange: (listener) => {
      listener("loading")
      return () => undefined
    },
    retry: vi.fn(),
    dispose: vi.fn(),
  }
  return {
    renderer,
    mountSpy,
    renderSpy,
    select: (incidentId: string) => selections.forEach((listener) => listener(incidentId)),
    preview: (incidentId: string | null) => previews.forEach((listener) => listener(incidentId)),
  }
}

describe("IncidentQueuePage", () => {
  it("renders the map panel beside the API-ordered queue", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const harness = rendererHarness()
    const renderer = harness.renderer
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
    expect(harness.mountSpy).toHaveBeenCalledOnce()
  })

  it("synchronizes map selection to the queue row and queue selection back to the map", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const harness = rendererHarness()
    const wrapper = mount(IncidentQueuePage, {
      props: {
        loadIncidentQueue: loader,
        createIncidentMapRenderer: () => harness.renderer,
      },
    })
    loader.resolve(0, { ok: true, page: page() })
    await flushPromises()

    harness.select(incidentPageFixture.items[1].incidentId)
    await nextTick()

    const selectedRow = wrapper.find(`[data-incident-id="${incidentPageFixture.items[1].incidentId}"]`)
    expect(selectedRow.attributes("aria-pressed")).toBe("true")

    await wrapper.findAll("article")[0]?.trigger("click")
    await nextTick()

    const latestView = harness.renderSpy.mock.lastCall?.[0]
    expect(latestView?.selectedIncidentId).toBe(incidentPageFixture.items[0].incidentId)
  })

  it("keeps exactly one incident expanded while preserving API order", async () => {
    const loader = new ControllableLoadIncidentQueue()
    const detailLoader = new ControllableLoadIncidentDetail()
    const wrapper = mount(IncidentQueuePage, {
      props: {
        loadIncidentQueue: loader,
        loadIncidentDetail: detailLoader,
      },
    })
    loader.resolve(0, { ok: true, page: page() })
    await flushPromises()

    const firstId = incidentPageFixture.items[0].incidentId
    const secondId = incidentPageFixture.items[1].incidentId
    await wrapper.find(`[data-incident-id="${firstId}"]`).trigger("click")
    expect(wrapper.findAll("[data-incident-detail]")).toHaveLength(1)
    expect(detailLoader.requests[0]?.incidentId).toBe(firstId)

    await wrapper.find(`[data-incident-id="${secondId}"]`).trigger("click")
    expect(wrapper.findAll("[data-incident-detail]")).toHaveLength(1)
    expect(wrapper.find(`[data-incident-id="${firstId}"]`).classes()).not.toContain(
      "incident-queue-row--expanded",
    )
    expect(wrapper.find(`[data-incident-id="${secondId}"]`).classes()).toContain(
      "incident-queue-row--expanded",
    )
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
