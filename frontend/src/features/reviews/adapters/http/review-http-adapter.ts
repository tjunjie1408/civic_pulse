import type { ReviewPort, ReviewResolutionAction } from "../../application/review-port"
import type { ReviewResolutionRequest } from "../../domain/review"
import { decodeReviewDetail, decodeReviewList, decodeReviewMutation } from "./decode-review"

interface ReviewHttpAdapterDependencies {
  readonly baseUrl: string
  readonly fetch: typeof globalThis.fetch
}
function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  )
}

export class ReviewHttpAdapter implements ReviewPort {
  constructor(private readonly dependencies: ReviewHttpAdapterDependencies) {}

  async list(
    query: { readonly status: "pending" | "approved" | "rejected"; readonly limit: number; readonly offset: number },
    signal: AbortSignal,
  ) {
    let response: Response
    try {
      const params = new URLSearchParams({
        status: query.status,
        limit: String(query.limit),
        offset: String(query.offset),
      })
      response = await this.dependencies.fetch(`${this.dependencies.baseUrl}/reviews?${params}`, {
        method: "GET",
        signal,
      })
    } catch (error: unknown) {
      return { ok: false as const, error: { kind: isAbortError(error) ? "aborted" as const : "network" as const } }
    }
    if (!response.ok) {
      return { ok: false as const, error: { kind: "service" as const, status: response.status } }
    }
    try {
      return { ok: true as const, page: decodeReviewList(await response.json()) }
    } catch (error: unknown) {
      return { ok: false as const, error: { kind: isAbortError(error) ? "aborted" as const : "contract" as const } }
    }
  }

  async get(reviewId: string, signal: AbortSignal) {
    let response: Response
    try {
      response = await this.dependencies.fetch(
        `${this.dependencies.baseUrl}/reviews/${encodeURIComponent(reviewId)}`,
        { method: "GET", signal },
      )
    } catch (error: unknown) {
      return { ok: false as const, error: { kind: isAbortError(error) ? "aborted" as const : "network" as const } }
    }
    if (response.status === 404) return { ok: false as const, error: { kind: "missing" as const } }
    if (!response.ok) return { ok: false as const, error: { kind: "service" as const, status: response.status } }
    try {
      return { ok: true as const, detail: decodeReviewDetail(await response.json()) }
    } catch (error: unknown) {
      return { ok: false as const, error: { kind: isAbortError(error) ? "aborted" as const : "contract" as const } }
    }
  }

  async resolve(
    reviewId: string,
    action: ReviewResolutionAction,
    request: ReviewResolutionRequest,
    signal: AbortSignal,
  ) {
    let response: Response
    try {
      response = await this.dependencies.fetch(
        `${this.dependencies.baseUrl}/reviews/${encodeURIComponent(reviewId)}/${action}`,
        {
          method: "POST",
          signal,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reviewer_id: request.reviewerId, note: request.note }),
        },
      )
    } catch (error: unknown) {
      return { ok: false as const, error: { kind: isAbortError(error) ? "aborted" as const : "network" as const } }
    }
    if (response.status === 404) return { ok: false as const, error: { kind: "missing" as const } }
    if (response.status === 409) return { ok: false as const, error: { kind: "conflict" as const, status: response.status } }
    if (!response.ok) return { ok: false as const, error: { kind: "service" as const, status: response.status } }
    try {
      return { ok: true as const, mutation: decodeReviewMutation(await response.json()) }
    } catch (error: unknown) {
      return { ok: false as const, error: { kind: isAbortError(error) ? "aborted" as const : "contract" as const } }
    }
  }
}
