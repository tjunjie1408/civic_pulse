import type { ReviewDetailResult, ReviewPort } from "./review-port"

export class LoadReviewDetail {
  constructor(private readonly port: Pick<ReviewPort, "get">) {}

  execute(reviewId: string, signal: AbortSignal): Promise<ReviewDetailResult> {
    return this.port.get(reviewId, signal)
  }
}
