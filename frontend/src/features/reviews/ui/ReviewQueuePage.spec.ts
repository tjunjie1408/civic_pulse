import { flushPromises, mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import type { ReviewDetailResult, ReviewListResult, ReviewMutationResult } from "../application/review-port"
import { reviewDetailFixture, reviewSummaryFixture } from "../testing/review-fixtures"
import ReviewQueuePage from "./ReviewQueuePage.vue"

class FakeLoadReviewQueue {
  calls = 0

  execute(signal: AbortSignal): Promise<ReviewListResult> {
    void signal
    this.calls += 1
    return Promise.resolve({
      ok: true,
      page: {
        items: this.calls === 1 ? [reviewSummaryFixture] : [],
        limit: 50,
        offset: 0,
        total: this.calls === 1 ? 1 : 0,
      },
    })
  }
}

class FakeLoadReviewDetail {
  execute(reviewId: string, signal: AbortSignal): Promise<ReviewDetailResult> {
    void signal
    return Promise.resolve(reviewId === reviewDetailFixture.reviewId
      ? { ok: true, detail: reviewDetailFixture }
      : { ok: false, error: { kind: "missing" } })
  }
}

class FakeResolveReview {
  readonly calls: Array<{
    readonly reviewId: string
    readonly action: "approve" | "reject"
    readonly reviewerId: string
    readonly note: string | null
  }> = []

  execute(
    reviewId: string,
    action: "approve" | "reject",
    request: { readonly reviewerId: string; readonly note: string | null },
    signal: AbortSignal,
  ): Promise<ReviewMutationResult> {
    void signal
    this.calls.push({ reviewId, action, reviewerId: request.reviewerId, note: request.note })
    return Promise.resolve({ ok: false, error: { kind: "service", status: 503 } })
  }
}

describe("ReviewQueuePage", () => {
  it("loads one review, shows the neutral evidence map, and sends the officer decision", async () => {
    const loader = new FakeLoadReviewQueue()
    const resolver = new FakeResolveReview()
    const wrapper = mount(ReviewQueuePage, {
      props: {
        loadReviewQueue: loader,
        loadReviewDetail: new FakeLoadReviewDetail(),
        resolveReview: resolver,
      },
    })
    await flushPromises()

    await wrapper.get(`[data-review-id="${reviewSummaryFixture.reviewId}"]`).trigger("click")
    await flushPromises()
    expect(wrapper.find("[data-review-evidence-map]").exists()).toBe(true)
    expect(wrapper.text()).toContain("Photo")
    expect(wrapper.text()).toContain("Attached")
    expect(wrapper.text()).not.toContain("field-photo.jpg")

    await wrapper.get("input[name=reviewer-id]").setValue("officer-7")
    await wrapper.get("textarea[name=review-note]").setValue("Checked field evidence")
    await wrapper.get(".review-resolution__reject").trigger("click")
    await flushPromises()

    expect(resolver.calls).toEqual([{
      reviewId: reviewSummaryFixture.reviewId,
      action: "reject",
      reviewerId: "officer-7",
      note: "Checked field evidence",
    }])
    expect(loader.calls).toBe(1)
    wrapper.unmount()
  })
})
