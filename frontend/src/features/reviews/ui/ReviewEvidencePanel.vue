<script setup lang="ts">
import { ref } from "vue"

import type { ReviewResolutionAction } from "../application/review-port"
import type {
  ReviewDetail,
  ReviewResolutionRequest,
} from "../domain/review"
import type { ReviewResolutionState } from "./use-review-queue"
import ReviewEvidenceMap from "./ReviewEvidenceMap.vue"

const props = defineProps<{
  readonly detail: ReviewDetail
  readonly resolutionState: ReviewResolutionState
}>()

const emit = defineEmits<{
  (event: "resolve", payload: {
    readonly action: ReviewResolutionAction
    readonly request: ReviewResolutionRequest
  }): void
}>()

const reviewerId = ref("")
const note = ref("")
const validationMessage = ref<string | null>(null)

function submit(action: ReviewResolutionAction): void {
  const normalizedReviewerId = reviewerId.value.trim()
  if (normalizedReviewerId.length === 0) {
    validationMessage.value = "Reviewer ID is required before recording a decision."
    return
  }
  validationMessage.value = null
  emit("resolve", {
    action,
    request: {
      reviewerId: normalizedReviewerId,
      note: note.value.trim() === "" ? null : note.value.trim(),
    },
  })
}

function formatCoordinate(value: number): string {
  return value.toFixed(5)
}

function formatDate(value: string): string {
  return `${new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(new Date(value))} UTC`
}

function errorMessage(kind: ReviewResolutionState["kind"]): string {
  return kind === "failed" ? "The decision could not be recorded. The review may have changed; retry." : ""
}
</script>

<template>
  <section
    :id="`review-detail-${detail.reviewId}`"
    class="review-evidence-panel"
    :aria-labelledby="`review-detail-heading-${detail.reviewId}`"
    data-review-detail
  >
    <header class="review-evidence-panel__header">
      <div>
        <p class="review-evidence-panel__eyebrow">
          Evidence boundary
        </p>
        <h2 :id="`review-detail-heading-${detail.reviewId}`">
          Review the relationship
        </h2>
      </div>
      <p class="review-evidence-panel__status">
        {{ detail.status }}
      </p>
    </header>

    <div class="review-evidence-panel__grid">
      <article
        v-for="(complaint, index) in [detail.complaintA, detail.complaintB]"
        :key="complaint.complaintId"
        class="review-complaint"
      >
        <p class="review-complaint__label">
          Complaint {{ index === 0 ? "A" : "B" }}
        </p>
        <p class="review-complaint__text">
          {{ complaint.text }}
        </p>
        <dl class="review-complaint__facts">
          <div><dt>Category</dt><dd>{{ complaint.category }}</dd></div>
          <div><dt>Reported</dt><dd>{{ formatDate(complaint.reportedAt) }}</dd></div>
          <div><dt>Coordinates</dt><dd>{{ formatCoordinate(complaint.latitude) }}, {{ formatCoordinate(complaint.longitude) }}</dd></div>
          <div><dt>Photo</dt><dd>{{ complaint.photoAvailable ? "Attached" : "Not attached" }}</dd></div>
        </dl>
      </article>
    </div>

    <div class="review-evidence-panel__map-section">
      <div>
        <p class="review-evidence-panel__eyebrow">
          Location evidence
        </p>
        <h3>Two complaint locations</h3>
        <p class="review-evidence-panel__muted">
          This view shows only the submitted points and their relationship. It does not imply an incident radius or priority.
        </p>
      </div>
      <ReviewEvidenceMap :detail="detail" />
    </div>

    <section
      class="review-matcher-evidence"
      aria-labelledby="matcher-evidence-heading"
    >
      <p class="review-evidence-panel__eyebrow">
        Matcher evidence
      </p>
      <h3 id="matcher-evidence-heading">
        Original recommendation: {{ detail.originalMatcherRecommendation }}
      </h3>
      <ul>
        <li
          v-for="reason in detail.matcherReasons"
          :key="reason"
        >
          {{ reason }}
        </li>
      </ul>
      <dl
        v-if="detail.matcherEvidence !== null"
        class="review-matcher-evidence__facts"
      >
        <div><dt>Semantic similarity</dt><dd>{{ detail.matcherEvidence.semanticSimilarity.toFixed(3) }}</dd></div>
        <div><dt>Geographic distance</dt><dd>{{ detail.matcherEvidence.geoDistanceMetres.toFixed(1) }} m</dd></div>
        <div><dt>Time difference</dt><dd>{{ detail.matcherEvidence.timeDifferenceSeconds.toFixed(0) }} s</dd></div>
        <div><dt>Category compatible</dt><dd>{{ detail.matcherEvidence.categoryCompatibility ? "Yes" : "No" }}</dd></div>
        <div><dt>Location compatibility</dt><dd>{{ detail.matcherEvidence.locationCompatibility }}</dd></div>
      </dl>
    </section>

    <form
      v-if="detail.status === 'pending'"
      class="review-resolution"
      @submit.prevent="submit('approve')"
    >
      <div>
        <p class="review-evidence-panel__eyebrow">
          Officer decision
        </p>
        <h3>Record the final relationship</h3>
        <p class="review-evidence-panel__muted">
          Approve confirms the match; reject keeps the complaints separate. The original matcher recommendation remains unchanged.
        </p>
      </div>
      <label>
        Reviewer ID
        <input
          v-model="reviewerId"
          name="reviewer-id"
          autocomplete="username"
          required
        >
      </label>
      <label>
        Note <span class="review-resolution__optional">(optional)</span>
        <textarea
          v-model="note"
          name="review-note"
          rows="3"
        />
      </label>
      <p
        v-if="validationMessage"
        class="review-resolution__error"
        role="alert"
      >
        {{ validationMessage }}
      </p>
      <p
        v-if="props.resolutionState.kind === 'failed'"
        class="review-resolution__error"
        role="alert"
      >
        {{ errorMessage(props.resolutionState.kind) }}
      </p>
      <div class="review-resolution__actions">
        <button
          type="button"
          class="review-resolution__reject"
          :disabled="props.resolutionState.kind === 'submitting'"
          @click="submit('reject')"
        >
          {{ props.resolutionState.kind === 'submitting' ? "Saving…" : "Reject match" }}
        </button>
        <button
          type="submit"
          class="review-resolution__approve"
          :disabled="props.resolutionState.kind === 'submitting'"
        >
          {{ props.resolutionState.kind === 'submitting' ? "Saving…" : "Approve match" }}
        </button>
      </div>
    </form>

    <p
      v-else
      class="review-evidence-panel__muted review-evidence-panel__resolved"
    >
      This review was resolved by {{ detail.reviewerId ?? "an officer" }}.
    </p>
  </section>
</template>

<style scoped>
.review-evidence-panel {
  padding: var(--space-5) clamp(var(--space-4), 3vw, var(--space-6));
  border-left: 0.25rem solid var(--civic-blue);
  background: #fbfcfd;
}

.review-evidence-panel__header,
.review-evidence-panel__map-section,
.review-resolution__actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.review-evidence-panel__header h2,
.review-evidence-panel__map-section h3,
.review-matcher-evidence h3,
.review-resolution h3 {
  margin: 0;
  font-size: 1.05rem;
}

.review-evidence-panel__eyebrow,
.review-complaint__label {
  margin: 0 0 var(--space-1);
  color: var(--slate);
  font-size: var(--text-label);
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.review-evidence-panel__status {
  margin: 0;
  color: var(--oxblood);
  font-size: var(--text-small);
  font-weight: 700;
  text-transform: uppercase;
}

.review-evidence-panel__grid,
.review-matcher-evidence__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  margin-top: var(--space-5);
}

.review-complaint,
.review-matcher-evidence,
.review-resolution {
  padding: var(--space-4);
  border: 1px solid var(--divider);
  background: var(--paper-white);
}

.review-complaint__text {
  min-height: 3rem;
  margin: var(--space-3) 0;
}

.review-complaint__facts,
.review-matcher-evidence__facts {
  margin-bottom: 0;
}

.review-complaint__facts {
  display: grid;
  gap: var(--space-2);
}

.review-complaint__facts div,
.review-matcher-evidence__facts div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}

dt {
  color: var(--slate);
  font-size: var(--text-label);
  text-transform: uppercase;
}

dd {
  margin: 0;
  font-size: var(--text-small);
  text-align: right;
}

.review-evidence-panel__map-section {
  display: grid;
  grid-template-columns: minmax(12rem, 0.65fr) minmax(0, 1.35fr);
  margin-top: var(--space-5);
}

.review-evidence-panel__map-section h3 {
  margin-bottom: var(--space-2);
}

.review-evidence-panel__muted {
  margin: var(--space-2) 0 0;
  color: var(--slate);
  font-size: var(--text-small);
}

.review-evidence-panel__map-section > :deep(.review-evidence-map) {
  min-height: 13rem;
}

.review-matcher-evidence,
.review-resolution {
  margin-top: var(--space-5);
}

.review-matcher-evidence ul {
  margin: var(--space-3) 0 0;
  padding-left: 1.25rem;
}

.review-matcher-evidence__facts {
  margin-top: var(--space-4);
}

.review-resolution {
  display: grid;
  gap: var(--space-3);
}

.review-resolution label {
  display: grid;
  gap: var(--space-1);
  color: var(--slate);
  font-size: var(--text-small);
  font-weight: 600;
}

.review-resolution input,
.review-resolution textarea {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid var(--divider);
  border-radius: 2px;
  background: var(--paper-white);
  color: var(--graphite);
}

.review-resolution__optional {
  font-weight: 400;
}

.review-resolution__error {
  margin: 0;
  color: var(--oxblood);
  font-size: var(--text-small);
}

.review-resolution__actions {
  justify-content: flex-end;
}

.review-resolution__actions button {
  min-height: 2.4rem;
  padding: 0.45rem 0.85rem;
  border: 1px solid;
  border-radius: 2px;
  cursor: pointer;
  font-weight: 700;
}

.review-resolution__actions button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.review-resolution__reject {
  border-color: var(--oxblood) !important;
  background: var(--paper-white);
  color: var(--oxblood);
}

.review-resolution__approve {
  border-color: var(--civic-blue) !important;
  background: var(--civic-blue);
  color: var(--paper-white);
}

.review-evidence-panel__resolved {
  margin-bottom: 0;
}

@media (max-width: 48rem) {
  .review-evidence-panel__header,
  .review-evidence-panel__map-section,
  .review-resolution__actions {
    display: flex;
    flex-direction: column;
  }

  .review-evidence-panel__grid,
  .review-evidence-panel__map-section {
    grid-template-columns: minmax(0, 1fr);
  }

  .review-evidence-panel__map-section > :deep(.review-evidence-map) {
    width: 100%;
  }

  .review-resolution__actions button {
    width: 100%;
  }
}
</style>
