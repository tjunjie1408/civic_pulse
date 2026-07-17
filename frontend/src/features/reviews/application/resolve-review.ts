import type {
  ReviewMutationResult,
  ReviewPort,
  ReviewResolutionAction,
} from "./review-port"
import type { ReviewResolutionRequest } from "../domain/review"

export class ResolveReview {
  constructor(private readonly port: Pick<ReviewPort, "resolve">) {}

  execute(
    reviewId: string,
    action: ReviewResolutionAction,
    request: ReviewResolutionRequest,
    signal: AbortSignal,
  ): Promise<ReviewMutationResult> {
    return this.port.resolve(reviewId, action, request, signal)
  }
}
