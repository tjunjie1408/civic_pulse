import { flushPromises, mount } from "@vue/test-utils"
import { afterEach, describe, expect, it } from "vitest"

import type { PhotoUploadResult } from "./features/submissions/application/photo-upload-port"
import type { ComplaintSubmissionResult } from "./features/submissions/application/complaint-port"
import {
  incidentDetailFixture,
  incidentPageFixture,
} from "./features/incidents/testing/incident-fixtures"
import type { IncidentDetailResult } from "./features/incidents/application/incident-detail-port"
import type { IncidentListResult } from "./features/incidents/application/incident-list-port"
import {
  reviewDetailFixture,
  reviewSummaryFixture,
} from "./features/reviews/testing/review-fixtures"
import type {
  ReviewDetailResult,
  ReviewListResult,
  ReviewMutationResult,
} from "./features/reviews/application/review-port"
import App from "./App.vue"

class FakeLoadIncidentQueue {
  execute(signal: AbortSignal): Promise<IncidentListResult> {
    void signal
    return Promise.resolve({ ok: true, page: incidentPageFixture })
  }
}

class FakeLoadIncidentDetail {
  execute(incidentId: string, signal: AbortSignal): Promise<IncidentDetailResult> {
    void signal
    return Promise.resolve(
      incidentId === incidentDetailFixture.incidentId
        ? { ok: true, detail: incidentDetailFixture }
        : { ok: false, error: { kind: "missing" } },
    )
  }
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

class FakeLoadReviewQueue {
  execute(signal: AbortSignal): Promise<ReviewListResult> {
    void signal
    return Promise.resolve({
      ok: true,
      page: { items: [reviewSummaryFixture], limit: 50, offset: 0, total: 1 },
    })
  }
}

class FakeLoadReviewDetail {
  execute(reviewId: string, signal: AbortSignal): Promise<ReviewDetailResult> {
    void signal
    return Promise.resolve(
      reviewId === reviewDetailFixture.reviewId
        ? { ok: true, detail: reviewDetailFixture }
        : { ok: false, error: { kind: "missing" } },
    )
  }
}

class FakeResolveReview {
  execute(
    reviewId: string,
    action: "approve" | "reject",
    request: { readonly reviewerId: string; readonly note: string | null },
    signal: AbortSignal,
  ): Promise<ReviewMutationResult> {
    void reviewId
    void action
    void request
    void signal
    return Promise.resolve({ ok: false, error: { kind: "service", status: 501 } })
  }
}

class FakeUploadPhoto {
  execute(file: File, signal: AbortSignal): Promise<PhotoUploadResult> {
    void file
    void signal
    return Promise.resolve({ ok: false, error: { kind: "service", status: 501 } })
  }
}

class FakeSubmitComplaint {
  execute(
    request: unknown,
    idempotencyKey: string,
    signal: AbortSignal,
  ): Promise<ComplaintSubmissionResult> {
    void request
    void idempotencyKey
    void signal
    return Promise.resolve({ ok: false, error: { kind: "service", status: 501 } })
  }
}

const reviewProps = {
  loadReviewQueue: new FakeLoadReviewQueue(),
  loadReviewDetail: new FakeLoadReviewDetail(),
  resolveReview: new FakeResolveReview(),
  submitComplaint: new FakeSubmitComplaint(),
  uploadPhoto: new FakeUploadPhoto(),
}

afterEach(() => {
  window.history.replaceState({}, "", "/")
})

describe("App shell", () => {
  it("provides the CivicPulse incident operations landmarks", async () => {
    const wrapper = mount(App, {
      props: {
        loadIncidentQueue: new FakeLoadIncidentQueue(),
        loadIncidentDetail: new FakeLoadIncidentDetail(),
        ...reviewProps,
      },
    })
    const banner = wrapper.find("header")

    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain("CivicPulse")
    expect(wrapper.get("h1").text()).toBe("Incident operations")
    expect(wrapper.find("main").exists()).toBe(true)
    await flushPromises()
    expect(wrapper.get(".incident-queue").text()).toContain("Active incident queue")
    expect(wrapper.findAll(".incident-queue-row")).toHaveLength(2)
    wrapper.unmount()
  })

  it("opens the native snapshot detail route from the expanded queue row", async () => {
    const wrapper = mount(App, {
      props: {
        loadIncidentQueue: new FakeLoadIncidentQueue(),
        loadIncidentDetail: new FakeLoadIncidentDetail(),
        ...reviewProps,
      },
    })
    await flushPromises()

    await wrapper.find(`[data-incident-id="${incidentDetailFixture.incidentId}"]`).trigger("click")
    await flushPromises()
    await wrapper.get("[data-open-full-incident]").trigger("click")

    expect(window.location.pathname).toBe(`/incidents/${incidentDetailFixture.incidentId}`)
    expect(wrapper.find("[data-incident-detail-ready]").exists()).toBe(true)
    expect(wrapper.find(".incident-queue").exists()).toBe(false)
    wrapper.unmount()
  })

  it("returns a stale direct detail route to the queue without choosing a successor", async () => {
    const detailLoader = new ControllableLoadIncidentDetail()
    window.history.replaceState({}, "", `/incidents/${incidentDetailFixture.incidentId}`)
    const wrapper = mount(App, {
      props: {
        loadIncidentQueue: new FakeLoadIncidentQueue(),
        loadIncidentDetail: detailLoader,
        ...reviewProps,
      },
    })

    expect(detailLoader.requests).toHaveLength(1)
    detailLoader.requests[0]?.resolve({ ok: false, error: { kind: "missing" } })
    await flushPromises()

    expect(window.location.pathname).toBe("/")
    expect(wrapper.get(".incident-queue").text()).toContain(
      "no successor was selected automatically",
    )
    expect(wrapper.find("[data-incident-detail-ready]").exists()).toBe(false)
    wrapper.unmount()
  })

  it("navigates to the separate pending review view", async () => {
    const wrapper = mount(App, {
      props: {
        loadIncidentQueue: new FakeLoadIncidentQueue(),
        loadIncidentDetail: new FakeLoadIncidentDetail(),
        ...reviewProps,
      },
    })

    await wrapper.get(".app-shell__nav button:nth-child(2)").trigger("click")
    await flushPromises()

    expect(window.location.pathname).toBe("/reviews")
    expect(wrapper.find(".review-queue").text()).toContain("Pending review queue")
    expect(wrapper.find(".incident-queue").exists()).toBe(false)
    wrapper.unmount()
  })

  it("navigates to the complaint submission view", async () => {
    const wrapper = mount(App, {
      props: {
        loadIncidentQueue: new FakeLoadIncidentQueue(),
        loadIncidentDetail: new FakeLoadIncidentDetail(),
        ...reviewProps,
      },
    })

    await wrapper.get(".app-shell__nav button:nth-child(3)").trigger("click")

    expect(window.location.pathname).toBe("/submit")
    expect(wrapper.get(".submit-page").text()).toContain("Submit a civic report")
    wrapper.unmount()
  })
})