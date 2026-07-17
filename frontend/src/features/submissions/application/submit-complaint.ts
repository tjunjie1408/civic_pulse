import type {
  ComplaintPort,
  ComplaintSubmissionResult,
} from "./complaint-port"
import type { ComplaintSubmissionRequest } from "../domain/complaint"

export class SubmitComplaint {
  constructor(private readonly port: Pick<ComplaintPort, "submit">) {}

  execute(
    request: ComplaintSubmissionRequest,
    idempotencyKey: string,
    signal: AbortSignal,
  ): Promise<ComplaintSubmissionResult> {
    return this.port.submit(request, idempotencyKey, signal)
  }
}
