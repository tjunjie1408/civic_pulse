import { flushPromises, mount } from "@vue/test-utils"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ComplaintSubmissionResult } from "../application/complaint-port"
import type { ComplaintSubmissionRequest } from "../domain/complaint"
import SubmitPage from "./SubmitPage.vue"

const result: ComplaintSubmissionResult = {
  ok: true,
  submission: {
    complaint: {
      complaintId: "00000000-0000-4000-8000-000000000001",
      text: "Blocked drain near the market",
      latitude: 3.07,
      longitude: 101.52,
      reportedAt: "2026-07-17T00:00:00Z",
      category: "blocked_drain",
      photoPath: "field-photo.jpg",
    },
    created: true,
    replayed: false,
    relationshipDecisions: [],
    incidentTransition: { previousIncidentSnapshotIds: [], currentIncidentSnapshotIds: [] },
    incidents: [],
    priorities: [],
  },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("SubmitPage", () => {
  it("previews a selected image and submits its filename reference", async () => {
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:photo-preview"),
      revokeObjectURL: vi.fn(),
    })
    const requests: ComplaintSubmissionRequest[] = []
    const submitComplaint = {
      execute: (request: ComplaintSubmissionRequest, key: string, signal: AbortSignal) => {
        void key
        void signal
        requests.push(request)
        return Promise.resolve(result)
      },
    }
    const wrapper = mount(SubmitPage, { props: { submitComplaint } })
    const file = new File(["fake image"], "field-photo.jpg", { type: "image/jpeg" })

    await wrapper.get("textarea").setValue("Blocked drain near the market")
    await wrapper.get("input[placeholder='3.07000']").setValue("3.07")
    await wrapper.get("input[placeholder='101.52000']").setValue("101.52")
    const photoInput = wrapper.get<HTMLInputElement>("input[type=file]")
    Object.defineProperty(photoInput.element, "files", { value: [file] })
    await photoInput.trigger("change")
    await flushPromises()

    expect(wrapper.find("[data-photo-preview]").attributes("src")).toBe("blob:photo-preview")
    await wrapper.get("form").trigger("submit")
    await flushPromises()

    expect(requests[0]?.photoPath).toBe("field-photo.jpg")
    expect(wrapper.find("[data-submission-result]").text()).toContain("Report saved")
    wrapper.unmount()
  })
})
