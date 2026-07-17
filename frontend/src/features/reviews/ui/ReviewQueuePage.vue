<script setup lang="ts">
import { computed, onMounted } from "vue"

import type { LoadReviewDetail } from "../application/load-review-detail"
import type { LoadReviewQueue } from "../application/load-review-queue"
import type { ReviewError, ReviewResolutionAction } from "../application/review-port"
import type { ResolveReview } from "../application/resolve-review"
import type { ReviewResolutionRequest } from "../domain/review"
import ReviewEvidencePanel from "./ReviewEvidencePanel.vue"
import ReviewSummaryRow from "./ReviewSummaryRow.vue"
import { useReviewQueue } from "./use-review-queue"

const props = defineProps<{
  readonly loadReviewQueue: Pick<LoadReviewQueue, "execute">
  readonly loadReviewDetail: Pick<LoadReviewDetail, "execute">
  readonly resolveReview: Pick<ResolveReview, "execute">
}>()

const emit = defineEmits<{
  (event: "back-to-queue"): void
}>()

const queue = useReviewQueue(props.loadReviewQueue, props.loadReviewDetail, props.resolveReview)
const queueState = computed(() => queue.state.value)
const queueDetailState = computed(() => queue.detailState.value)
const queueResolutionState = computed(() => queue.resolutionState.value)
const expandedReviewId = computed(() => queue.expandedReviewId.value)
const queueError = computed(() => queueState.value.kind === "failed" ? queueState.value.error : null)
const currentPage = computed(() => {
  switch (queue.state.value.kind) {
    case "ready":
    case "empty":
      return queue.state.value.page
    case "loading":
    case "failed":
      return queue.state.value.previous
  }
})
const reviews = computed(() => currentPage.value?.items ?? [])
const isLoading = computed(() => queue.state.value.kind === "loading")
const hasInitialFailure = computed(
  () => queue.state.value.kind === "failed" && queue.state.value.previous === null,
)
const hasRefreshFailure = computed(
  () => queue.state.value.kind === "failed" && queue.state.value.previous !== null,
)
const isEmpty = computed(() => queue.state.value.kind === "empty")
const resultSummary = computed(() => {
  const page = currentPage.value
  if (page === null) return "Current result count unavailable"
  return page.total > page.items.length
    ? `Showing ${page.items.length} of ${page.total}`
    : `${page.items.length} pending review${page.items.length === 1 ? "" : "s"}`
})

function errorMessage(error: ReviewError): string {
  switch (error.kind) {
    case "network": return "The review service could not be reached."
    case "service": return `The review service returned HTTP ${error.status}.`
    case "contract": return "The review service returned an unexpected response."
    case "missing": return "This review is no longer available."
    case "conflict": return "This review changed before the decision was recorded."
    case "aborted": return ""
  }
}

function resolve(
  reviewId: string,
  payload: { readonly action: ReviewResolutionAction; readonly request: ReviewResolutionRequest },
): void {
  void queue.resolve(reviewId, payload.action, payload.request)
}

onMounted(() => {
  void queue.load()
})
</script>

<template>
  <section
    class="review-queue"
    aria-labelledby="review-queue-heading"
    :aria-busy="isLoading"
  >
    <header class="review-queue__header">
      <div>
        <p class="review-queue__eyebrow">
          Decision ledger
        </p>
        <h1 id="review-queue-heading">
          Pending review queue
        </h1>
        <p class="review-queue__description">
          Potential relationships stay separate from confirmed incidents until an officer records a decision.
        </p>
      </div>
      <div class="review-queue__controls">
        <p
          class="review-queue__result-count"
          aria-live="polite"
        >
          {{ resultSummary }}
        </p>
        <button
          v-if="!isLoading && !hasInitialFailure"
          type="button"
          @click="queue.retry"
        >
          Refresh
        </button>
        <button
          type="button"
          class="review-queue__back"
          @click="emit('back-to-queue')"
        >
          Incident queue
        </button>
      </div>
    </header>

    <div
      v-if="queueResolutionState.kind === 'succeeded'"
      class="review-queue__success"
      role="status"
    >
      <div>
        <strong>Decision recorded: {{ queueResolutionState.mutation.finalRelationshipState }}</strong>
        <p>Candidate evidence has been updated using the officer decision. The pending review list was refreshed.</p>
      </div>
      <div class="review-queue__snapshot-result">
        <div>
          <span>Previous incident snapshots</span>
          <ul>
            <li
              v-for="snapshotId in queueResolutionState.mutation.previousIncidentSnapshotIds"
              :key="`previous-${snapshotId}`"
            >
              {{ snapshotId }}
            </li>
            <li v-if="queueResolutionState.mutation.previousIncidentSnapshotIds.length === 0">
              None
            </li>
          </ul>
        </div>
        <div>
          <span>New incident snapshots</span>
          <ul>
            <li
              v-for="snapshotId in queueResolutionState.mutation.newIncidentSnapshotIds"
              :key="`new-${snapshotId}`"
            >
              {{ snapshotId }}
            </li>
            <li v-if="queueResolutionState.mutation.newIncidentSnapshotIds.length === 0">
              None
            </li>
          </ul>
        </div>
      </div>
      <button
        type="button"
        @click="queue.clearResolution"
      >
        Dismiss
      </button>
    </div>

    <p
      v-if="isLoading && currentPage === null"
      class="review-queue__loading"
      role="status"
    >
      Loading pending reviews…
    </p>
    <p
      v-if="isEmpty"
      class="review-queue__empty"
      role="status"
    >
      No pending relationships require officer review.
    </p>

    <div
      v-if="hasInitialFailure"
      class="review-queue__failure"
      role="alert"
    >
      <p>Unable to load pending reviews. {{ queueError === null ? "" : errorMessage(queueError) }}</p>
      <button
        type="button"
        @click="queue.retry"
      >
        Retry
      </button>
    </div>
    <div
      v-if="hasRefreshFailure"
      class="review-queue__failure"
      role="alert"
    >
      <p>Could not refresh pending reviews. Showing the last known queue. {{ queueError === null ? "" : errorMessage(queueError) }}</p>
      <button
        type="button"
        @click="queue.retry"
      >
        Retry
      </button>
    </div>

    <ol
      v-if="reviews.length > 0"
      class="review-queue__list"
      aria-label="Pending reviews"
    >
      <ReviewSummaryRow
        v-for="review in reviews"
        :key="review.reviewId"
        :review="review"
        :expanded="review.reviewId === expandedReviewId"
        @toggle="queue.toggle"
      >
        <div
          v-if="review.reviewId === expandedReviewId"
          class="review-queue__detail-wrap"
        >
          <p
            v-if="queueDetailState.kind === 'loading'"
            class="review-queue__detail-status"
            role="status"
          >
            Loading review evidence…
          </p>
          <p
            v-else-if="queueDetailState.kind === 'missing'"
            class="review-queue__detail-status"
            role="status"
          >
            This review is no longer available.
          </p>
          <div
            v-else-if="queueDetailState.kind === 'failed'"
            class="review-queue__detail-status"
            role="alert"
          >
            <p>Unable to load this review. {{ errorMessage(queueDetailState.error) }}</p>
            <button
              type="button"
              @click="queue.retryDetail"
            >
              Retry evidence
            </button>
          </div>
          <ReviewEvidencePanel
            v-else-if="queueDetailState.kind === 'ready' && queueDetailState.reviewId === review.reviewId"
            :detail="queueDetailState.detail"
            :resolution-state="queueResolutionState"
            @resolve="resolve(review.reviewId, $event)"
          />
        </div>
      </ReviewSummaryRow>
    </ol>
  </section>
</template>

<style scoped>
.review-queue {
  overflow: hidden;
  border: 1px solid var(--divider);
  background: var(--paper-white);
}

.review-queue__header,
.review-queue__controls,
.review-queue__success,
.review-queue__failure {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.review-queue__header {
  padding: var(--space-5) clamp(var(--space-4), 3vw, var(--space-6));
  border-bottom: 1px solid var(--divider);
}

.review-queue__eyebrow {
  margin: 0 0 var(--space-2);
  color: var(--slate);
  font-size: var(--text-label);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.review-queue h1 {
  margin: 0;
  font-size: clamp(1.35rem, 2vw, 1.75rem);
  line-height: var(--leading-tight);
}

.review-queue__description {
  max-width: 42rem;
  margin: var(--space-2) 0 0;
  color: var(--slate);
  font-size: var(--text-small);
}

.review-queue__controls {
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.review-queue__result-count {
  margin: 0;
  color: var(--slate);
  font-size: var(--text-small);
  font-variant-numeric: tabular-nums;
}

.review-queue__controls button,
.review-queue__failure button,
.review-queue__success button {
  min-height: 2.25rem;
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--civic-blue);
  border-radius: 2px;
  background: var(--paper-white);
  color: var(--civic-blue);
  cursor: pointer;
  font-weight: 600;
}

.review-queue__back {
  background: var(--civic-blue) !important;
  color: var(--paper-white) !important;
}

.review-queue__loading,
.review-queue__empty {
  margin: 0;
  padding: var(--space-6);
  color: var(--slate);
}

.review-queue__failure {
  margin: var(--space-4) clamp(var(--space-4), 3vw, var(--space-6));
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--oxblood);
  background: #fbf5f6;
}

.review-queue__failure p {
  margin: 0;
  color: var(--oxblood);
}

.review-queue__success {
  align-items: flex-start;
  padding: var(--space-4) clamp(var(--space-4), 3vw, var(--space-6));
  border-bottom: 1px solid var(--divider);
  background: #f0f7f3;
}

.review-queue__success p {
  margin: var(--space-1) 0 0;
  color: var(--slate);
  font-size: var(--text-small);
}

.review-queue__snapshot-result {
  display: flex;
  gap: var(--space-5);
  color: var(--slate);
  font-size: var(--text-label);
}

.review-queue__snapshot-result span {
  font-weight: 700;
  text-transform: uppercase;
}

.review-queue__snapshot-result ul {
  max-width: 15rem;
  margin: var(--space-1) 0 0;
  padding-left: 1rem;
  color: var(--graphite);
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 0.68rem;
  overflow-wrap: anywhere;
}

.review-queue__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.review-queue__detail-wrap {
  border-top: 1px solid var(--divider);
}

.review-queue__detail-status {
  margin: 0;
  padding: var(--space-5);
  color: var(--slate);
}

.review-queue__detail-status button {
  margin-top: var(--space-2);
  padding: 0.35rem 0.65rem;
  border: 1px solid var(--civic-blue);
  border-radius: 2px;
  background: var(--paper-white);
  color: var(--civic-blue);
  cursor: pointer;
  font-weight: 600;
}

@media (max-width: 64rem) {
  .review-queue__header,
  .review-queue__success {
    align-items: flex-start;
    flex-direction: column;
  }

  .review-queue__controls {
    justify-content: flex-start;
  }
}

@media (max-width: 48rem) {
  .review-queue__controls,
  .review-queue__snapshot-result {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
