import { describe, expect, it } from "vitest"

import {
  decodeReviewDetail,
  decodeReviewList,
  decodeReviewMutation,
} from "./decode-review"
import {
  reviewDetailTransportFixture,
  reviewMutationTransportFixture,
  reviewSummaryTransportFixture,
} from "../../testing/review-fixtures"

describe("review response decoder", () => {
  it("decodes ordered summaries and preserves safe complaint photo availability", () => {
    const page = decodeReviewList({
      items: [reviewSummaryTransportFixture],
      limit: 50,
      offset: 0,
      total: 1,
    })

    expect(page.items[0]?.reviewId).toBe(reviewSummaryTransportFixture.review_id)

    const detail = decodeReviewDetail(reviewDetailTransportFixture)
    expect(detail.complaintA.photoAvailable).toBe(false)
    expect(detail.complaintB.photoAvailable).toBe(true)
    expect(Object.hasOwn(detail.complaintB, "photoPath")).toBe(false)
    expect(detail.matcherEvidence?.semanticSimilarity).toBe(0.94)
  })

  it("rejects extra fields rather than accepting an unbounded transport shape", () => {
    expect(() => decodeReviewDetail({ ...reviewDetailTransportFixture, photo_path: "unsafe" })).toThrow(
      "Invalid review response",
    )
  })

  it("preserves all many-to-many transition IDs and null conflict priority", () => {
    const mutation = decodeReviewMutation({
      ...reviewMutationTransportFixture,
      conflict_status: "conflict",
      affected_incidents: [
        { ...reviewMutationTransportFixture.affected_incidents[0], status: "conflict", priority: null },
      ],
      resulting_priorities: [null],
    })

    expect(mutation.previousIncidentSnapshotIds).toEqual([
      "00000000-0000-4000-8000-000000000010",
    ])
    expect(mutation.newIncidentSnapshotIds).toEqual([
      "00000000-0000-4000-8000-000000000011",
    ])
    expect(mutation.conflictStatus).toBe("conflict")
    expect(mutation.resultingPriorities).toEqual([null])
  })
})
