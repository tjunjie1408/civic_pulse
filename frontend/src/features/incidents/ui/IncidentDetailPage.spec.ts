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
  it("renders a photo thumbnail linking to the stored image", async () => {
    const loader = new ControllableDetailLoader()
    const detailWithPhoto = {
      ...incidentDetailFixture,
      confirmedReports: {
        ...incidentDetailFixture.confirmedReports,
        items: [
          {
            ...incidentDetailFixture.confirmedReports.items[0],
            photoUrl: "/api/v1/photos/30000000-0000-0000-0000-000000000001",
          },
        ],
      },
    }
    const wrapper = mount(IncidentDetailPage, {
      props: { snapshotId: detailWithPhoto.incidentId, loadIncidentDetail: loader },
    })

    expect(loader.requests).toHaveLength(1)
    loader.requests[0]?.resolve({ ok: true, detail: detailWithPhoto })
    await flushPromises()

    expect(wrapper.get("h1").text()).toContain("Full incident")
    expect(wrapper.text()).toContain("Street light is out near the community hall")
    expect(wrapper.text()).toContain("More confirmed reports are available")
    expect(wrapper.get("[data-back-to-queue]").text()).toContain("Back to incident queue")
    expect(wrapper.get("[data-report-photo]").attributes("src")).toBe(
      "/api/v1/photos/30000000-0000-0000-0000-000000000001",
    )
    expect(wrapper.get("[data-report-photo]").attributes("loading")).toBe("lazy")
    expect(wrapper.get("[data-report-photo-link]").attributes("href")).toBe(
      "/api/v1/photos/30000000-0000-0000-0000-000000000001",
    )
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

  it("explains legacy photo references without an image", async () => {
    const loader = new ControllableDetailLoader()
    const detailWithLegacyPhoto = {
      ...incidentDetailFixture,
      confirmedReports: {
        ...incidentDetailFixture.confirmedReports,
        items: [
          {
            ...incidentDetailFixture.confirmedReports.items[0],
            photoUrl: null,
            photoAvailable: true,
          },
        ],
      },
    }
    const wrapper = mount(IncidentDetailPage, {
      props: { snapshotId: detailWithLegacyPhoto.incidentId, loadIncidentDetail: loader },
    })

    expect(loader.requests).toHaveLength(1)
    loader.requests[0]?.resolve({ ok: true, detail: detailWithLegacyPhoto })
    await flushPromises()

    expect(wrapper.text()).toContain("Photo reference recorded before server storage")
    expect(wrapper.find("[data-report-photo]").exists()).toBe(false)
  })
})
