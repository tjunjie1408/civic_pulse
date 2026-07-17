import type { ComplaintPort, ComplaintSubmissionResult } from "../../application/complaint-port"
import type { ComplaintSubmissionRequest } from "../../domain/complaint"
import { decodeComplaintSubmission } from "./decode-complaint-submission"

interface ComplaintHttpAdapterDependencies {
  readonly baseUrl: string
  readonly fetch: typeof globalThis.fetch
}

function isAbortError(error: unknown): boolean {
  return typeof error === "object" && error !== null && "name" in error && error.name === "AbortError"
}

export class ComplaintHttpAdapter implements ComplaintPort {
  constructor(private readonly dependencies: ComplaintHttpAdapterDependencies) {}

  async submit(
    request: ComplaintSubmissionRequest,
    idempotencyKey: string,
    signal: AbortSignal,
  ): Promise<ComplaintSubmissionResult> {
    let response: Response
    try {
      response = await this.dependencies.fetch(`${this.dependencies.baseUrl}/complaints`, {
        method: "POST",
        signal,
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({
          text: request.text,
          latitude: request.latitude,
          longitude: request.longitude,
          reported_at: request.reportedAt,
          category: request.category,
          photo_path: request.photoPath,
        }),
      })
    } catch (error: unknown) {
      return { ok: false, error: { kind: isAbortError(error) ? "aborted" : "network" } }
    }
    if (response.status === 409) return { ok: false, error: { kind: "conflict", status: response.status } }
    if (!response.ok) return { ok: false, error: { kind: "service", status: response.status } }
    try {
      return { ok: true, submission: decodeComplaintSubmission(await response.json()) }
    } catch (error: unknown) {
      return { ok: false, error: { kind: isAbortError(error) ? "aborted" : "contract" } }
    }
  }
}
