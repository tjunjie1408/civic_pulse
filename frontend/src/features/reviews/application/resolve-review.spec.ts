import { describe, expect, it } from "vitest"

import type { ReviewMutationResult } from "./review-port"
import { ResolveReview } from "./resolve-review"

describe("ResolveReview", () => {
  it("passes the officer action and bounded resolution request to the port", async () => {
    const result: ReviewMutationResult = {
      ok: false,
      error: { kind: "conflict", status: 409 },
    }
    const port = {
      resolve: (
        reviewId: string,
        action: string,
        request: { reviewerId: string; note: string | null },
        signal: AbortSignal,
      ) => {
        expect(reviewId).toBe("review-1")
        expect(action).toBe("reject")
        expect(request).toEqual({ reviewerId: "officer-1", note: null })
        expect(signal.aborted).toBe(false)
        return Promise.resolve(result)
      },
    }

    await expect(
      new ResolveReview(port).execute(
        "review-1",
        "reject",
        { reviewerId: "officer-1", note: null },
        new AbortController().signal,
      ),
    ).resolves.toBe(result)
  })
})
