import { onScopeDispose, readonly, shallowRef } from "vue"
import type { ShallowRef } from "vue"

import type { ComplaintError } from "../application/complaint-port"
import type { SubmitComplaint } from "../application/submit-complaint"
import type { ComplaintSubmission, ComplaintSubmissionRequest } from "../domain/complaint"

export type ComplaintSubmissionState =
  | { readonly kind: "idle" }
  | { readonly kind: "submitting"; readonly request: ComplaintSubmissionRequest }
  | {
      readonly kind: "failed"
      readonly request: ComplaintSubmissionRequest
      readonly error: Exclude<ComplaintError, { kind: "aborted" }>
    }
  | { readonly kind: "succeeded"; readonly submission: ComplaintSubmission }

export interface ComplaintSubmissionController {
  readonly state: Readonly<ShallowRef<ComplaintSubmissionState>>
  readonly submit: (request: ComplaintSubmissionRequest) => Promise<void>
  readonly retry: () => Promise<void>
  readonly reset: () => void
}

export function useComplaintSubmission(
  submitComplaint: Pick<SubmitComplaint, "execute">,
  createIdempotencyKey: () => string = () => crypto.randomUUID(),
): ComplaintSubmissionController {
  const state = shallowRef<ComplaintSubmissionState>({ kind: "idle" })
  let idempotencyKey = createIdempotencyKey()
  let activeController: AbortController | null = null
  let requestId = 0

  const submit = async (request: ComplaintSubmissionRequest): Promise<void> => {
    activeController?.abort()
    const controller = new AbortController()
    const currentRequestId = ++requestId
    activeController = controller
    state.value = { kind: "submitting", request }

    const result = await submitComplaint.execute(request, idempotencyKey, controller.signal)
    if (currentRequestId !== requestId || controller.signal.aborted) return
    activeController = null
    if (!result.ok) {
      if (result.error.kind !== "aborted") {
        state.value = { kind: "failed", request, error: result.error }
      }
      return
    }
    state.value = { kind: "succeeded", submission: result.submission }
    idempotencyKey = createIdempotencyKey()
  }

  const retry = async (): Promise<void> => {
    if (state.value.kind === "failed") {
      await submit(state.value.request)
    }
  }

  const reset = (): void => {
    activeController?.abort()
    activeController = null
    requestId += 1
    state.value = { kind: "idle" }
  }

  onScopeDispose(() => {
    activeController?.abort()
    requestId += 1
  })

  return {
    state: readonly(state),
    submit,
    retry,
    reset,
  }
}
