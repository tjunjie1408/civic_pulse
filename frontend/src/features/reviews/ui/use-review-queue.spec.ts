import { effectScope } from "vue"
import { describe, expect, it } from "vitest"

import type {
  ReviewDetailResult,
  ReviewListResult,
  ReviewMutationResult,
} from "../application/review-port"
import type { ReviewMutation, ReviewResolutionRequest } from "../domain/review"
import {
  reviewDetailFixture,
  reviewSummaryFixture,
} from "../testing/review-fixtures"
import { useReviewQueue } from "./use-review-queue"

interface PendingListRequest {
  readonly signal: AbortSignal
  readonly resolve: (result: ReviewListResult) => void
}

interface PendingDetailRequest {
  readonly reviewId: string
  readonly signal: AbortSignal
  readonly resolve: (result: ReviewDetailResult) => void
}

interface ResolutionCall {
  readonly reviewId: string
  readonly action: "approve" | "reject"
  readonly request: ReviewResolutionRequest
}

class ControllableLoadReviewQueue {
  readonly requests: PendingListRequest[] = []

  execute(signal: AbortSignal): Promise<ReviewListResult> {
    return new Promise((resolve) => this.requests.push({ signal, resolve }))
  }
}

class ControllableLoadReviewDetail {
  readonly requests: PendingDetailRequest[] = []

  execute(reviewId: string, signal: AbortSignal): Promise<ReviewDetailResult> {
    return new Promise((resolve) => this.requests.push({ reviewId, signal, resolve }))
  }
}

class ControllableResolveReview {
  readonly calls: ResolutionCall[] = []
  readonly requests: Array<{ resolve: (result: ReviewMutationResult) => void }> = []

  execute(
    reviewId: string,
    action: "approve" | "reject",
    request: ReviewResolutionRequest,
    signal: AbortSignal,
  ): Promise<ReviewMutationResult> {
    void signal
    this.calls.push({ reviewId, action, request })
    return new Promise((resolve) => this.requests.push({ resolve }))
  }
}

const resolvedMutation: ReviewMutation = {
  review: {
    ...reviewDetailFixture,
    status: "approved",
    resolvedAt: "2026-07-13T02:00:00Z",
    reviewerId: "demo-officer",
    reviewNote: "Same physical incident.",
    finalRelationshipState: "auto_match",
    decisionSource: "officer_review",
    graphVersion: "graph-v2",
    previousIncidentSnapshotIds: ["00000000-0000-4000-8000-000000000010"],
    newIncidentSnapshotIds: ["00000000-0000-4000-8000-000000000011"],
  },
  finalRelationshipState: "auto_match",
  affectedComplaintIds: [reviewDetailFixture.complaintA.complaintId, reviewDetailFixture.complaintB.complaintId],
  previousIncidentSnapshotIds: ["00000000-0000-4000-8000-000000000010"],
  newIncidentSnapshotIds: ["00000000-0000-4000-8000-000000000011"],
  affectedIncidents: [],
  resultingPriorities: [],
  conflictStatus: null,
}

function createQueue() {
  const loader = new ControllableLoadReviewQueue()
  const detailLoader = new ControllableLoadReviewDetail()
  const resolver = new ControllableResolveReview()
  const scope = effectScope()
  const queue = scope.run(() => useReviewQueue(loader, detailLoader, resolver))
  if (queue === undefined) throw new Error("The review queue must be created in an effect scope")
  return { loader, detailLoader, resolver, queue, scope }
}

describe("useReviewQueue", () => {
  it("preserves API order and permits exactly one expanded review", async () => {
    const { loader, detailLoader, queue, scope } = createQueue()
    const page = { items: [reviewSummaryFixture], limit: 50, offset: 0, total: 1 }
    const load = queue.load()
    loader.requests[0]?.resolve({ ok: true, page })
    await load

    const expand = queue.toggle(reviewSummaryFixture.reviewId)
    expect(queue.expandedReviewId.value).toBe(reviewSummaryFixture.reviewId)
    detailLoader.requests[0]?.resolve({ ok: true, detail: reviewDetailFixture })
    await expand

    expect(queue.detailState.value.kind).toBe("ready")
    await queue.toggle(reviewSummaryFixture.reviewId)
    expect(queue.expandedReviewId.value).toBeNull()
    expect(queue.detailState.value).toEqual({ kind: "idle" })
    scope.stop()
  })

  it("ignores a late detail response after another review is expanded", async () => {
    const { detailLoader, queue, scope } = createQueue()
    const first = queue.toggle("review-a")
    const second = queue.toggle("review-b")

    expect(detailLoader.requests[0]?.signal.aborted).toBe(true)
    detailLoader.requests[1]?.resolve({ ok: true, detail: { ...reviewDetailFixture, reviewId: "review-b" } })
    await second
    detailLoader.requests[0]?.resolve({ ok: true, detail: reviewDetailFixture })
    await first

    expect(queue.detailState.value.kind).toBe("ready")
    expect(queue.detailState.value.kind === "ready" ? queue.detailState.value.reviewId : null).toBe("review-b")
    scope.stop()
  })

  it("records the requested decision and preserves all returned snapshot IDs", async () => {
    const { loader, detailLoader, resolver, queue, scope } = createQueue()
    const initialPage = { items: [reviewSummaryFixture], limit: 50, offset: 0, total: 1 }
    const load = queue.load()
    loader.requests[0]?.resolve({ ok: true, page: initialPage })
    await load
    const expand = queue.toggle(reviewSummaryFixture.reviewId)
    detailLoader.requests[0]?.resolve({ ok: true, detail: reviewDetailFixture })
    await expand

    const resolving = queue.resolve(reviewSummaryFixture.reviewId, "approve", {
      reviewerId: "officer-7",
      note: "Confirmed at same location",
    })
    expect(resolver.calls[0]).toEqual({
      reviewId: reviewSummaryFixture.reviewId,
      action: "approve",
      request: { reviewerId: "officer-7", note: "Confirmed at same location" },
    })
    resolver.requests[0]?.resolve({
      ok: true,
      mutation: resolvedMutation,
    })
    await Promise.resolve()
    loader.requests[1]?.resolve({ ok: true, page: { items: [], limit: 50, offset: 0, total: 0 } })
    await resolving

    expect(queue.resolutionState.value.kind).toBe("succeeded")
    expect(queue.resolutionState.value.kind === "succeeded"
      ? queue.resolutionState.value.mutation.previousIncidentSnapshotIds
      : []).toEqual(["00000000-0000-4000-8000-000000000010"])
    expect(queue.resolutionState.value.kind === "succeeded"
      ? queue.resolutionState.value.mutation.newIncidentSnapshotIds
      : []).toEqual(["00000000-0000-4000-8000-000000000011"])
    scope.stop()
  })
})
