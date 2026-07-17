import type { ReviewListResult, ReviewPort } from "./review-port"

export class LoadReviewQueue {
  constructor(private readonly port: Pick<ReviewPort, "list">) {}

  execute(signal: AbortSignal): Promise<ReviewListResult> {
    return this.port.list({ status: "pending", limit: 50, offset: 0 }, signal)
  }
}
