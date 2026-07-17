import type {
  ReviewDetail,
  ReviewMutation,
  ReviewPage,
  ReviewResolutionRequest,
  ReviewStatus,
} from "../domain/review"

export interface ReviewListQuery {
  readonly status: ReviewStatus
  readonly limit: number
  readonly offset: number
}
export type ReviewError =
  | { readonly kind: "network" }
  | { readonly kind: "service"; readonly status: number }
  | { readonly kind: "contract" }
  | { readonly kind: "missing" }
  | { readonly kind: "conflict"; readonly status: number }
  | { readonly kind: "aborted" }

export type ReviewListResult =
  | { readonly ok: true; readonly page: ReviewPage }
  | { readonly ok: false; readonly error: Exclude<ReviewError, { kind: "missing" | "conflict" }> }

export type ReviewDetailResult =
  | { readonly ok: true; readonly detail: ReviewDetail }
  | { readonly ok: false; readonly error: ReviewError }

export type ReviewMutationResult =
  | { readonly ok: true; readonly mutation: ReviewMutation }
  | { readonly ok: false; readonly error: ReviewError }

export type ReviewResolutionAction = "approve" | "reject"

export interface ReviewPort {
  list(query: ReviewListQuery, signal: AbortSignal): Promise<ReviewListResult>
  get(reviewId: string, signal: AbortSignal): Promise<ReviewDetailResult>
  resolve(
    reviewId: string,
    action: ReviewResolutionAction,
    request: ReviewResolutionRequest,
    signal: AbortSignal,
  ): Promise<ReviewMutationResult>
}
