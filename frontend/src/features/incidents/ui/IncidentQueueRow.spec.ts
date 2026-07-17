import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import type {
  IncidentSummary,
  OperationalPriorityLevel,
} from "../domain/incident"
import { incidentPageFixture } from "../testing/incident-fixtures"
import { incidentDetailFixture } from "../testing/incident-fixtures"
import IncidentQueueRow from "./IncidentQueueRow.vue"

const templateIncident = incidentPageFixture.items[0]

function incident(overrides: Partial<IncidentSummary> = {}): IncidentSummary {
  return { ...templateIncident, ...overrides }
}

describe("IncidentQueueRow", () => {
  it("renders every category as an equal category label", () => {
    const wrapper = mount(IncidentQueueRow, {
      props: {
        incident: incident({ categories: ["flooding", "blocked_drain", "other"] }),
      },
    })

    expect(wrapper.find("li").exists()).toBe(true)
    expect(wrapper.find("article").exists()).toBe(true)
    expect(wrapper.get("h2").text()).toBe("Flooding · Blocked drain · Other")
    expect(wrapper.text()).not.toContain("Primary")
    expect(wrapper.text()).not.toContain("Dominant")
  })

  it.each<[OperationalPriorityLevel, string]>([
    ["critical", "Critical operational priority"],
    ["high", "High operational priority"],
    ["medium", "Medium operational priority"],
    ["low", "Low operational priority"],
  ])("renders the %s priority label", (level, label) => {
    const wrapper = mount(IncidentQueueRow, {
      props: {
        incident: incident({
          priority: { level, reasons: [], policyVersion: "priority-v1" },
        }),
      },
    })

    expect(wrapper.get(".incident-queue-row__priority").text()).toBe(label)
  })

  it("renders the exact neutral label when operational priority is unavailable", () => {
    const wrapper = mount(IncidentQueueRow, {
      props: { incident: incident({ priority: null }) },
    })

    expect(wrapper.get(".incident-queue-row__priority").text()).toBe(
      "No operational priority",
    )
  })

  it("keeps evidence facts separate and the abbreviated snapshot secondary", () => {
    const wrapper = mount(IncidentQueueRow, {
      props: {
        incident: incident({
          incidentId: "ffffffff-ffff-4fff-8fff-ffffffffffff",
          status: "confirmed",
          confirmedReportCount: 3,
          pendingCandidateCount: 1,
          radiusMetres: 125.5,
          latestReportedAt: "2026-07-16T03:00:00Z",
        }),
      },
    })

    const facts = wrapper.findAll(".incident-queue-row__fact")
    expect(facts.map((fact) => ({
      term: fact.get("dt").text(),
      value: fact.get("dd").text(),
    }))).toEqual([
      { term: "Status", value: "Confirmed" },
      { term: "Confirmed reports", value: "3" },
      { term: "Pending review candidates", value: "1" },
      { term: "Affected radius", value: "125.5 m" },
      { term: "Latest update", value: "16 Jul 2026, 03:00 UTC" },
    ])
    expect(wrapper.get("time").attributes("datetime")).toBe("2026-07-16T03:00:00Z")

    const snapshot = wrapper.get("small.incident-queue-row__snapshot")
    expect(snapshot.text()).toBe("Snapshot ffffffff")
    expect(snapshot.text()).not.toContain("ffffffff-ffff-4fff-8fff-ffffffffffff")
  })

  it("exposes selected state and emits selection from click and keyboard activation", async () => {
    const wrapper = mount(IncidentQueueRow, {
      props: { incident: incident(), selected: true },
    })
    const entry = wrapper.get("article")

    expect(entry.attributes("role")).toBe("button")
    expect(entry.attributes("tabindex")).toBe("0")
    expect(entry.attributes("aria-pressed")).toBe("true")
    expect(entry.classes()).toContain("incident-queue-row--selected")

    await entry.trigger("click")
    await entry.trigger("keydown", { key: "Enter" })
    await entry.trigger("keydown", { key: " " })

    expect(wrapper.emitted("select")).toHaveLength(3)
    expect(wrapper.emitted("select")?.every((event) => event[0] === incident().incidentId)).toBe(true)
  })

  it("emits preview state from pointer and keyboard focus", async () => {
    const wrapper = mount(IncidentQueueRow, {
      props: { incident: incident(), hovered: true },
    })
    const entry = wrapper.get("article")

    expect(entry.classes()).toContain("incident-queue-row--hovered")
    await entry.trigger("mouseenter")
    await entry.trigger("focus")
    await entry.trigger("mouseleave")
    await entry.trigger("blur")

    expect(wrapper.emitted("preview")).toEqual([
      [incident().incidentId],
      [incident().incidentId],
      [null],
      [null],
    ])
  })

  it("renders a bounded confirmed-report preview only when expanded", async () => {
    const wrapper = mount(IncidentQueueRow, {
      props: {
        incident: incident({ incidentId: incidentDetailFixture.incidentId }),
        expanded: true,
        detail: incidentDetailFixture,
      },
    })

    expect(wrapper.get("[data-incident-detail]").text()).toContain(
      "Street light is out near the community hall",
    )
    expect(wrapper.get("[data-confirmed-report-count]").text()).toContain("4")
    expect(wrapper.get("[data-confirmed-report-more]").text()).toContain("More reports")

    await wrapper.get("[data-open-full-incident]").trigger("click")
    expect(wrapper.emitted("open-detail")).toEqual([[incidentDetailFixture.incidentId]])
  })
})
