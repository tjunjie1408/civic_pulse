import { describe, expect, it } from "vitest"

import type { ReviewListResult } from "./review-port"
import { LoadReviewQueue } from "./load-review-queue"

describe("LoadReviewQueue", () => {
  it("loads the pending API-owned review page", async () => {
    const result: ReviewListResult = { ok: true, page: { items: [], limit: 50, offset: 0, total: 0 } }
    const port = {
      list: (query: { status: string; limit: number; offset: number }, signal: AbortSignal) => {
        expect(query).toEqual({ status: "pending", limit: 50, offset: 0 })
        expect(signal.aborted).toBe(false)
        return Promise.resolve(result)
      },
    }

    await expect(new LoadReviewQueue(port).execute(new AbortController().signal)).resolves.toBe(result)
  })
})
