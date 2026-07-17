import { onScopeDispose, readonly, ref, shallowRef } from "vue"
import type { Ref, ShallowRef } from "vue"

import type { LoadReviewDetail } from "../application/load-review-detail"
import type { ReviewError, ReviewResolutionAction } from "../application/review-port"
import type { LoadReviewQueue } from "../application/load-review-queue"
import type { ResolveReview } from "../application/resolve-review"
import type {
  ReviewDetail,
  ReviewMutation,
  ReviewPage,
  ReviewResolutionRequest,
} from "../domain/review"

export type ReviewQueueState =
  | { readonly kind: "loading"; readonly previous: ReviewPage | null }
  | { readonly kind: "ready"; readonly page: ReviewPage }
  | { readonly kind: "empty"; readonly page: ReviewPage }
  | {
      readonly kind: "failed"
      readonly previous: ReviewPage | null
      readonly error: Exclude<ReviewError, { kind: "aborted" | "missing" | "conflict" }>
    }

export type ReviewDetailState =
  | { readonly kind: "idle" }
  | { readonly kind: "loading"; readonly reviewId: string }
  | { readonly kind: "ready"; readonly reviewId: string; readonly detail: ReviewDetail }
  | { readonly kind: "missing"; readonly reviewId: string }
  | {
      readonly kind: "failed"
      readonly reviewId: string
      readonly error: Exclude<ReviewError, { kind: "aborted" }>
    }

export type ReviewResolutionState =
  | { readonly kind: "idle" }
  | {
      readonly kind: "submitting"
      readonly reviewId: string
      readonly action: ReviewResolutionAction
    }
  | { readonly kind: "succeeded"; readonly mutation: ReviewMutation }
  | { readonly kind: "failed"; readonly error: Exclude<ReviewError, { kind: "aborted" }> }

export interface ReviewQueueController {
  readonly state: Readonly<ShallowRef<ReviewQueueState>>
  readonly detailState: Readonly<ShallowRef<ReviewDetailState>>
  readonly resolutionState: Readonly<ShallowRef<ReviewResolutionState>>
  readonly expandedReviewId: Readonly<Ref<string | null>>
  readonly load: () => Promise<void>
  readonly retry: () => Promise<void>
  readonly toggle: (reviewId: string) => Promise<void>
  readonly retryDetail: () => Promise<void>
  readonly resolve: (
    reviewId: string,
    action: ReviewResolutionAction,
    request: ReviewResolutionRequest,
  ) => Promise<void>
  readonly clearResolution: () => void
}

export function useReviewQueue(
  loadReviewQueue: Pick<LoadReviewQueue, "execute">,
  loadReviewDetail: Pick<LoadReviewDetail, "execute">,
  resolveReview: Pick<ResolveReview, "execute">,
): ReviewQueueController {
  const state = shallowRef<ReviewQueueState>({ kind: "loading", previous: null })
  const detailState = shallowRef<ReviewDetailState>({ kind: "idle" })
  const resolutionState = shallowRef<ReviewResolutionState>({ kind: "idle" })
  const expandedReviewId = ref<string | null>(null)
  let listController: AbortController | null = null
  let detailController: AbortController | null = null
  let resolutionController: AbortController | null = null
  let listRequestId = 0
  let detailRequestId = 0
  let resolutionRequestId = 0

  const previousPage = (): ReviewPage | null => {
    switch (state.value.kind) {
      case "ready":
      case "empty":
        return state.value.page
      case "loading":
      case "failed":
        return state.value.previous
    }
  }

  const load = async (): Promise<void> => {
    const previous = previousPage()
    listController?.abort()
    const controller = new AbortController()
    const currentRequestId = ++listRequestId
    listController = controller
    state.value = { kind: "loading", previous }

    const result = await loadReviewQueue.execute(controller.signal)
    if (currentRequestId !== listRequestId || controller.signal.aborted) return
    listController = null
    if (result.ok) {
      state.value = result.page.items.length === 0
        ? { kind: "empty", page: result.page }
        : { kind: "ready", page: result.page }
      if (expandedReviewId.value !== null && !result.page.items.some(
        (review) => review.reviewId === expandedReviewId.value,
      )) {
        expandedReviewId.value = null
        detailController?.abort()
        detailState.value = { kind: "idle" }
      }
      return
    }
    if (result.error.kind !== "aborted") {
      state.value = { kind: "failed", previous, error: result.error }
    }
  }

  const loadDetail = async (reviewId: string): Promise<void> => {
    detailController?.abort()
    const controller = new AbortController()
    const currentRequestId = ++detailRequestId
    detailController = controller
    detailState.value = { kind: "loading", reviewId }
    const result = await loadReviewDetail.execute(reviewId, controller.signal)
    if (currentRequestId !== detailRequestId || controller.signal.aborted) return
    detailController = null
    if (result.ok) {
      detailState.value = { kind: "ready", reviewId, detail: result.detail }
    } else if (result.error.kind === "missing") {
      detailState.value = { kind: "missing", reviewId }
    } else if (result.error.kind !== "aborted") {
      detailState.value = { kind: "failed", reviewId, error: result.error }
    }
  }

  const toggle = async (reviewId: string): Promise<void> => {
    if (expandedReviewId.value === reviewId) {
      expandedReviewId.value = null
      detailController?.abort()
      detailController = null
      detailState.value = { kind: "idle" }
      return
    }

    expandedReviewId.value = reviewId
    await loadDetail(reviewId)
  }

  const retryDetail = async (): Promise<void> => {
    if (expandedReviewId.value !== null) {
      await loadDetail(expandedReviewId.value)
    }
  }

  const resolve = async (
    reviewId: string,
    action: ReviewResolutionAction,
    request: ReviewResolutionRequest,
  ): Promise<void> => {
    resolutionController?.abort()
    const controller = new AbortController()
    const currentRequestId = ++resolutionRequestId
    resolutionController = controller
    resolutionState.value = { kind: "submitting", reviewId, action }
    const result = await resolveReview.execute(reviewId, action, request, controller.signal)
    if (currentRequestId !== resolutionRequestId || controller.signal.aborted) return
    resolutionController = null
    if (!result.ok) {
      if (result.error.kind !== "aborted") {
        resolutionState.value = { kind: "failed", error: result.error }
      }
      return
    }
    resolutionState.value = { kind: "succeeded", mutation: result.mutation }
    expandedReviewId.value = null
    detailState.value = { kind: "idle" }
    detailController?.abort()
    detailController = null
    await load()
  }

  onScopeDispose(() => {
    listRequestId += 1
    detailRequestId += 1
    resolutionRequestId += 1
    listController?.abort()
    detailController?.abort()
    resolutionController?.abort()
  })

  return {
    state: readonly(state),
    detailState: readonly(detailState),
    resolutionState: readonly(resolutionState),
    expandedReviewId: readonly(expandedReviewId),
    load,
    retry: load,
    toggle,
    retryDetail,
    resolve,
    clearResolution: () => { resolutionState.value = { kind: "idle" } },
  }
}
