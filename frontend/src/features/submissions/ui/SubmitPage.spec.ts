import { flushPromises, mount } from "@vue/test-utils"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ComplaintSubmissionResult } from "../application/complaint-port"
import type { ComplaintSubmissionRequest } from "../domain/complaint"
import SubmitPage from "./SubmitPage.vue"

const PHOTO_ID = "00000000-0000-4000-8000-000000000099"

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

function stubPhotoPreviewUrl(): void {
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:photo-preview"),
    revokeObjectURL: vi.fn(),
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("SubmitPage", () => {
  it("uploads the photo on selection and passes its id on submit", async () => {
    stubPhotoPreviewUrl()
    const requests: ComplaintSubmissionRequest[] = []
    const uploadPhoto = {
      execute: vi.fn().mockResolvedValue({ ok: true, photoId: PHOTO_ID }),
    }
    const submitComplaint = {
      execute: (request: ComplaintSubmissionRequest, key: string, signal: AbortSignal) => {
        void key
        void signal
        requests.push(request)
        return Promise.resolve(result)
      },
    }
    const wrapper = mount(SubmitPage, { props: { submitComplaint, uploadPhoto } })
    const file = new File(["fake image"], "field-photo.jpg", { type: "image/jpeg" })

    await wrapper.get("textarea").setValue("Blocked drain near the market")
    await wrapper.get("input[placeholder='3.07000']").setValue("3.07")
    await wrapper.get("input[placeholder='101.52000']").setValue("101.52")
    const photoInput = wrapper.get<HTMLInputElement>("input[type=file]")
    expect(photoInput.classes()).toContain("submit-page__file-input")
    expect(wrapper.get('[data-photo-picker]').text()).toBe("Upload photo")
    expect(wrapper.get('[data-photo-picker]').attributes("for")).toBe("report-photo")
    Object.defineProperty(photoInput.element, "files", { value: [file] })
    await photoInput.trigger("change")
    await flushPromises()

    expect(uploadPhoto.execute).toHaveBeenCalledTimes(1)
    expect(wrapper.find("[data-photo-preview]").attributes("src")).toBe("blob:photo-preview")
    expect(wrapper.get('[data-photo-picker]').text()).toBe("Choose another photo")
    expect(wrapper.get('button[type="submit"]').classes()).toContain("submit-page__button--primary")

    await wrapper.get("form").trigger("submit")
    await flushPromises()

    expect(requests[0]).toEqual({
      text: "Blocked drain near the market",
      latitude: 3.07,
      longitude: 101.52,
      reportedAt: requests[0]?.reportedAt,
      category: null,
      photoId: PHOTO_ID,
    })
    wrapper.unmount()
  })

  it("blocks submission while the photo upload is in flight", async () => {
    stubPhotoPreviewUrl()
    let resolveUpload: ((value: { ok: true; photoId: string }) => void) | undefined
    const uploadPhoto = {
      execute: vi.fn().mockImplementation(
        () =>
          new Promise<{ ok: true; photoId: string }>((resolve) => {
            resolveUpload = resolve
          }),
      ),
    }
    const submitComplaint = {
      execute: vi.fn().mockResolvedValue(result),
    }
    const wrapper = mount(SubmitPage, { props: { submitComplaint, uploadPhoto } })
    const file = new File(["fake image"], "field-photo.jpg", { type: "image/jpeg" })

    await wrapper.get("textarea").setValue("Blocked drain near the market")
    await wrapper.get("input[placeholder='3.07000']").setValue("3.07")
    await wrapper.get("input[placeholder='101.52000']").setValue("101.52")
    const photoInput = wrapper.get<HTMLInputElement>("input[type=file]")
    expect(photoInput.classes()).toContain("submit-page__file-input")
    expect(wrapper.get('[data-photo-picker]').text()).toBe("Upload photo")
    expect(wrapper.get('[data-photo-picker]').attributes("for")).toBe("report-photo")
    Object.defineProperty(photoInput.element, "files", { value: [file] })
    await photoInput.trigger("change")
    await flushPromises()

    const submitButton = wrapper.get("button[type='submit']")
    expect(submitButton.attributes("disabled")).toBeDefined()
    expect(submitButton.text()).toBe("Waiting for photo upload…")

    await wrapper.get("form").trigger("submit")
    await flushPromises()

    expect(submitComplaint.execute).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain("Wait for the photo upload to finish, or remove the photo.")

    resolveUpload?.({ ok: true, photoId: PHOTO_ID })
    await flushPromises()
    wrapper.unmount()
  })

  it("shows the upload error and submits without a photo after removal", async () => {
    stubPhotoPreviewUrl()
    const requests: ComplaintSubmissionRequest[] = []
    const uploadPhoto = {
      execute: vi.fn().mockResolvedValue({ ok: false, error: { kind: "service", status: 500 } }),
    }
    const submitComplaint = {
      execute: (request: ComplaintSubmissionRequest, key: string, signal: AbortSignal) => {
        void key
        void signal
        requests.push(request)
        return Promise.resolve(result)
      },
    }
    const wrapper = mount(SubmitPage, { props: { submitComplaint, uploadPhoto } })
    const file = new File(["fake image"], "field-photo.jpg", { type: "image/jpeg" })

    await wrapper.get("textarea").setValue("Blocked drain near the market")
    await wrapper.get("input[placeholder='3.07000']").setValue("3.07")
    await wrapper.get("input[placeholder='101.52000']").setValue("101.52")
    const photoInput = wrapper.get<HTMLInputElement>("input[type=file]")
    expect(photoInput.classes()).toContain("submit-page__file-input")
    expect(wrapper.get('[data-photo-picker]').text()).toBe("Upload photo")
    expect(wrapper.get('[data-photo-picker]').attributes("for")).toBe("report-photo")
    Object.defineProperty(photoInput.element, "files", { value: [file] })
    await photoInput.trigger("change")
    await flushPromises()

    expect(wrapper.text()).toContain("The photo could not be uploaded. Remove it or try again.")
    expect(wrapper.get("[data-retry-upload]").classes()).toContain("submit-page__button--secondary")
    expect(wrapper.get("[data-remove-photo]").classes()).toContain("submit-page__button--danger")

    const removePhoto = wrapper
      .findAll("button[type='button']")
      .find((candidate) => candidate.text() === "Remove photo")
    expect(removePhoto).toBeDefined()
    await removePhoto!.trigger("click")
    await flushPromises()

    expect(wrapper.text()).not.toContain("The photo could not be uploaded. Remove it or try again.")

    await wrapper.get("form").trigger("submit")
    await flushPromises()

    expect(requests[0]).toEqual({
      text: "Blocked drain near the market",
      latitude: 3.07,
      longitude: 101.52,
      reportedAt: requests[0]?.reportedAt,
      category: null,
      photoId: null,
    })
    wrapper.unmount()
  })
})