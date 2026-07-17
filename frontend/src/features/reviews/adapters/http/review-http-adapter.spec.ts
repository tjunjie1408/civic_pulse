import { describe, expect, it, vi } from "vitest"

import { ReviewHttpAdapter } from "./review-http-adapter"
import {
  reviewMutationTransportFixture,
  reviewSummaryTransportFixture,
} from "../../testing/review-fixtures"

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

describe("ReviewHttpAdapter", () => {
  it("requests pending reviews with explicit API-owned pagination", async () => {
    const fetchStub = vi.fn<typeof fetch>().mockResolvedValue(
      response({ items: [reviewSummaryTransportFixture], limit: 50, offset: 0, total: 1 }),
    )
    const adapter = new ReviewHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    const result = await adapter.list({ status: "pending", limit: 50, offset: 0 }, new AbortController().signal)

    expect(result.ok).toBe(true)
    const requestInit = fetchStub.mock.calls[0]?.[1]
    expect(fetchStub.mock.calls[0]?.[0]).toBe("/api/v1/reviews?status=pending&limit=50&offset=0")
    expect(requestInit?.method).toBe("GET")
    expect(requestInit?.signal).toBeInstanceOf(AbortSignal)
  })

  it("maps a missing review detail to an explicit missing result", async () => {
    const fetchStub = vi.fn<typeof fetch>().mockResolvedValue(response({ code: "missing" }, 404))
    const adapter = new ReviewHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    await expect(adapter.get("review-1", new AbortController().signal)).resolves.toEqual({
      ok: false,
      error: { kind: "missing" },
    })
  })

  it("posts a resolution action and preserves transition payloads", async () => {
    const fetchStub = vi.fn<typeof fetch>().mockResolvedValue(response(reviewMutationTransportFixture))
    const adapter = new ReviewHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    const result = await adapter.resolve(
      reviewSummaryTransportFixture.review_id,
      "approve",
      { reviewerId: "demo-officer", note: "Same physical incident." },
      new AbortController().signal,
    )

    expect(result.ok).toBe(true)
    expect(fetchStub).toHaveBeenCalledWith(
      `/api/v1/reviews/${reviewSummaryTransportFixture.review_id}/approve`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ reviewer_id: "demo-officer", note: "Same physical incident." }),
      }),
    )
    if (result.ok) {
      expect(result.mutation.newIncidentSnapshotIds).toHaveLength(1)
    }
  })
})
