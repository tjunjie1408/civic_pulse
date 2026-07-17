import type {
  ComplaintSubmission,
  ComplaintSubmissionRequest,
} from "../domain/complaint"

export type ComplaintError =
  | { readonly kind: "network" }
  | { readonly kind: "service"; readonly status: number }
  | { readonly kind: "conflict"; readonly status: number }
  | { readonly kind: "contract" }
  | { readonly kind: "aborted" }

export type ComplaintSubmissionResult =
  | { readonly ok: true; readonly submission: ComplaintSubmission }
  | { readonly ok: false; readonly error: ComplaintError }

export interface ComplaintPort {
  submit(
    request: ComplaintSubmissionRequest,
    idempotencyKey: string,
    signal: AbortSignal,
  ): Promise<ComplaintSubmissionResult>
}
