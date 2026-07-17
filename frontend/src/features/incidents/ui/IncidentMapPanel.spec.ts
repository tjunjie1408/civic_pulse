import { mount } from "@vue/test-utils"
import { describe, expect, it, vi } from "vitest"

import type { IncidentSummary } from "../domain/incident"
import type { HeatCell, HeatmapMode } from "../domain/heatmap"
import type { IncidentMapRenderer, MapRenderStrategy } from "../application/incident-map-port"
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
  readonly renders: Array<{ cells: readonly HeatCell[]; mode: HeatmapMode }>
  readonly mountSpy: ReturnType<typeof vi.fn>
  readonly disposeSpy: ReturnType<typeof vi.fn>
  readonly resizeSpy: ReturnType<typeof vi.fn>
}

function rendererSpy(strategy: MapRenderStrategy = "neutral-density"): RendererSpy {
  const renders: Array<{ cells: readonly HeatCell[]; mode: HeatmapMode }> = []
  const mountSpy = vi.fn<(container: HTMLElement) => void>()
  const renderSpy = vi.fn(
    (cells: readonly HeatCell[], mode: HeatmapMode): MapRenderStrategy => {
      renders.push({ cells, mode })
      return mode.kind === "all" ? strategy : "category-heat"
    },
  )
  const disposeSpy = vi.fn<() => void>()
  const resizeSpy = vi.fn<() => void>()
  return {
    renders,
    mountSpy,
    mount: mountSpy,
    render: renderSpy,
    resizeSpy,
    resize: resizeSpy,
    disposeSpy,
    dispose: disposeSpy,
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

  it("defaults to All and explains neutral total-density fallback", () => {
    const renderer = rendererSpy("neutral-density")
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident], createRenderer: () => renderer },
    })

    expect(wrapper.get("select").element.value).toBe("all")
    expect(wrapper.text()).toContain("Neutral total-density")
    expect(wrapper.text()).toContain("Flooding")
    expect(renderer.renders.at(-1)?.mode).toEqual({ kind: "all" })
  })

  it("selecting Flooding rebuilds cells independently and exposes the blue legend item", async () => {
    const renderer = rendererSpy("neutral-density")
    const wrapper = mount(IncidentMapPanel, {
      props: { incidents: [floodingIncident, drainIncident], createRenderer: () => renderer },
    })

    await wrapper.get("select").setValue("flooding")

    expect(renderer.renders.at(-1)?.mode).toEqual({ kind: "category", category: "flooding" })
    expect(renderer.renders.at(-1)?.cells).toEqual([
      expect.objectContaining({ dominantCategory: "flooding" }),
    ])
    expect(wrapper.get('[data-category="flooding"]').attributes("data-color")).toBe("#1677a8")
    expect(wrapper.text()).not.toContain("Neutral total-density")
  })

  it("keeps loading, empty, and recoverable queue states usable when the map has no cells", () => {
    const renderer = rendererSpy()
    const wrapper = mount(IncidentMapPanel, { props: { incidents: [], createRenderer: () => renderer } })

    expect(wrapper.get("[data-map-empty]").text()).toContain("No confirmed incident density")
    expect(wrapper.get("select").attributes("aria-label")).toBe("Heatmap category")
    expect(wrapper.get("[data-map-status]").attributes("role")).toBe("status")
  })
})
