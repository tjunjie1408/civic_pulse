import { mount } from "@vue/test-utils"
import { nextTick } from "vue"
import { describe, expect, it, vi } from "vitest"

import type {
  IncidentMapRenderer,
  IncidentMapView,
  MapLifecycleState,
  MapRenderStrategy,
} from "../application/incident-map-port"
import type { IncidentSummary } from "../domain/incident"
import IncidentMapPanel from "./IncidentMapPanel.vue"

const floodingIncident: IncidentSummary = {
  incidentId: "flooding-1",
  status: "confirmed",
  categories: ["flooding"],
  priority: { level: "high", reasons: [], policyVersion: "priority-v1" },
  confirmedReportCount: 2,
  pendingCandidateCount: 0,
  centroid: { latitude: 1.3521, longitude: 103.8198 },
  radiusMetres: 100,
  earliestReportedAt: "2026-07-16T01:00:00Z",
  latestReportedAt: "2026-07-16T02:00:00Z",
  conflictReasons: [],
}

const drainIncident: IncidentSummary = {
  ...floodingIncident,
  incidentId: "drain-1",
  categories: ["blocked_drain"],
  centroid: { latitude: 1.3531, longitude: 103.8208 },
}

interface RendererSpy extends IncidentMapRenderer {
  readonly renders: IncidentMapView[]
  readonly mountSpy: ReturnType<typeof vi.fn>
  readonly disposeSpy: ReturnType<typeof vi.fn>
  readonly resizeSpy: ReturnType<typeof vi.fn>
  readonly retrySpy: ReturnType<typeof vi.fn>
  readonly emitSelect: (incidentId: string) => void
  readonly emitPreview: (incidentId: string | null) => void
  readonly emitLifecycle: (state: MapLifecycleState) => void
}

function rendererSpy(strategy: MapRenderStrategy = "neutral-density"): RendererSpy {
  const renders: IncidentMapView[] = []
  const selectListeners = new Set<(incidentId: string) => void>()
  const previewListeners = new Set<(incidentId: string | null) => void>()
  const lifecycleListeners = new Set<(state: MapLifecycleState) => void>()
  const mountSpy = vi.fn<(container: HTMLElement) => void>()
  const renderSpy = vi.fn(
    (view: IncidentMapView): MapRenderStrategy => {
      renders.push(view)
      return view.mode.kind === "all" ? strategy : "category-heat"
    },
  )
  const disposeSpy = vi.fn<() => void>()
  const resizeSpy = vi.fn<() => void>()
  const retrySpy = vi.fn<() => void>()
  return {
    renders,
    mountSpy,
    mount: mountSpy,
    render: renderSpy,
    resizeSpy,
    resize: resizeSpy,
    onIncidentSelect: (listener) => {
      selectListeners.add(listener)
      return () => selectListeners.delete(listener)
    },
    onIncidentPreview: (listener) => {
      previewListeners.add(listener)
      return () => previewListeners.delete(listener)
    },
    onLifecycleChange: (listener) => {
      lifecycleListeners.add(listener)
      listener("loading")
      return () => lifecycleListeners.delete(listener)
    },
    retry: retrySpy,
    disposeSpy,
    dispose: disposeSpy,
    emitSelect: (incidentId) => selectListeners.forEach((listener) => listener(incidentId)),
    emitPreview: (incidentId) => previewListeners.forEach((listener) => listener(incidentId)),
    emitLifecycle: (state) => lifecycleListeners.forEach((listener) => listener(state)),
    retrySpy,
  }
}

describe("IncidentMapPanel", () => {
  it("renders a map panel beside the API-ordered queue", () => {
    const renderer = rendererSpy()
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident, drainIncident], createRenderer: () => renderer },
    })

    expect(wrapper.get("section").attributes("aria-labelledby")).toBe("incident-map-heading")
    expect(wrapper.get("h2").text()).toContain("Incident map")
    expect(wrapper.find("[data-map-container]").exists()).toBe(true)
    expect(renderer.mountSpy).toHaveBeenCalledOnce()
    expect(renderer.resizeSpy).toHaveBeenCalledOnce()

    window.dispatchEvent(new Event("resize"))
    expect(renderer.resizeSpy).toHaveBeenCalledTimes(2)

    wrapper.unmount()
    expect(renderer.disposeSpy).toHaveBeenCalledOnce()
  })

  it("defaults to All", () => {
    const renderer = rendererSpy("neutral-density")
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident], createRenderer: () => renderer },
    })

    expect(wrapper.get("select").element.value).toBe("all")
    expect(wrapper.text()).toContain("Flooding")
    expect(renderer.renders.at(-1)?.mode).toEqual({ kind: "all" })
  })

  it("selecting Flooding rebuilds cells independently", async () => {
    const renderer = rendererSpy("neutral-density")
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident, drainIncident], createRenderer: () => renderer },
    })

    await wrapper.get("select").setValue("flooding")

    expect(renderer.renders.at(-1)?.mode).toEqual({ kind: "category", category: "flooding" })
    expect(renderer.renders.at(-1)?.cells).toEqual([
      expect.objectContaining({ dominantCategory: "flooding" }),
    ])
  })

  it("renders a density legend independent of category filtering", async () => {
    const renderer = rendererSpy("neutral-density")
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident, drainIncident], createRenderer: () => renderer },
    })

    const legend = wrapper.get('[aria-label="Report density"]')
    expect(legend.attributes("role")).toBe("group")
    expect(legend.text()).toContain("Low")
    expect(legend.text()).toContain("High")
    expect(wrapper.find('[aria-label="Report density"] [data-density-gradient]').exists()).toBe(true)

    await wrapper.get("select").setValue("flooding")
    expect(wrapper.findAll('[aria-label="Report density"]')).toHaveLength(1)
  })

  it("keeps loading, empty, and recoverable queue states usable when the map has no cells", () => {
    const renderer = rendererSpy()
    const wrapper = mount(IncidentMapPanel, { props: { incidents: [], createRenderer: () => renderer } })

    expect(wrapper.get("[data-map-empty]").text()).toContain("No confirmed incident density")
    expect(wrapper.get("select").attributes("aria-label")).toBe("Heatmap category")
    expect(wrapper.get("[data-map-status]").attributes("role")).toBe("status")
  })

  it("announces the initial online map load until the style is ready", async () => {
    const renderer = rendererSpy()
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident], createRenderer: () => renderer },
    })

    expect(wrapper.get("[data-map-container]").attributes("aria-busy")).toBe("true")
    expect(wrapper.get("[data-map-loading]").text()).toContain("Loading street map")

    renderer.emitLifecycle("ready")
    await nextTick()

    expect(wrapper.get("[data-map-container]").attributes("aria-busy")).toBe("false")
    expect(wrapper.find("[data-map-loading]").exists()).toBe(false)
  })
  it("forwards map selection and preview events to the queue page", async () => {
    const renderer = rendererSpy()
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident], createRenderer: () => renderer },
    })

    renderer.emitSelect("flooding-1")
    renderer.emitPreview("flooding-1")
    await nextTick()

    expect(wrapper.emitted("select")).toEqual([["flooding-1"]])
    expect(wrapper.emitted("preview")).toEqual([["flooding-1"]])
  })

  it("keeps incident overlays available when the base map degrades and offers retry", async () => {
    const renderer = rendererSpy()
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident], createRenderer: () => renderer },
    })

    renderer.emitLifecycle("degraded")
    await nextTick()

    expect(wrapper.text()).toContain("Base map unavailable")
    const retry = wrapper.get("[data-map-retry]")
    expect(retry.classes()).toContain("incident-map-panel__retry")
    expect(retry.attributes("type")).toBe("button")
    await wrapper.get("[data-map-retry]").trigger("click")
    expect(renderer.retrySpy).toHaveBeenCalledOnce()

    renderer.emitLifecycle("recovering")
    await nextTick()
    expect(wrapper.text()).toContain("Restoring base map")
  })
})
