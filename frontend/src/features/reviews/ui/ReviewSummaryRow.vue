<script setup lang="ts">
import type { ReviewSummary } from "../domain/review"

const props = defineProps<{
  readonly review: ReviewSummary
  readonly expanded: boolean
}>()

const emit = defineEmits<{
  (event: "toggle", reviewId: string): void
}>()

function toggle(): void {
  emit("toggle", props.review.reviewId)
}
</script>

<template>
  <li class="review-summary-row">
    <button
      class="review-summary-row__button"
      type="button"
      :aria-expanded="props.expanded"
      :aria-controls="`review-detail-${review.reviewId}`"
      :data-review-id="review.reviewId"
      @click="toggle"
    >
      <span class="review-summary-row__main">
        <span class="review-summary-row__eyebrow">Matcher evidence requires officer review</span>
        <strong>{{ review.leftComplaintId.slice(0, 8) }} ↔ {{ review.rightComplaintId.slice(0, 8) }}</strong>
      </span>
      <span class="review-summary-row__facts">
        <span>{{ review.matcherReasons.length }} reason{{ review.matcherReasons.length === 1 ? "" : "s" }}</span>
        <time :datetime="review.createdAt">{{ review.createdAt }}</time>
        <span
          class="review-summary-row__chevron"
          aria-hidden="true"
        >{{ props.expanded ? "−" : "+" }}</span>
      </span>
    </button>
    <slot />
  </li>
</template>

<style scoped>
.review-summary-row {
  border-bottom: 1px solid var(--divider);
}

.review-summary-row__button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-4);
  padding: var(--space-5) clamp(var(--space-4), 3vw, var(--space-6));
  border: 0;
  border-left: 0.25rem solid var(--oxblood);
  background: var(--paper-white);
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: background-color 140ms ease;
}

.review-summary-row__button:hover,
.review-summary-row__button[aria-expanded="true"] {
  background: #fbf5f6;
}

.review-summary-row__main,
.review-summary-row__facts {
  display: grid;
  min-width: 0;
}

.review-summary-row__main {
  gap: var(--space-2);
}

.review-summary-row__main strong {
  font-size: 1.05rem;
}

.review-summary-row__eyebrow {
  color: var(--oxblood);
  font-size: var(--text-label);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.review-summary-row__facts {
  flex: 0 0 auto;
  grid-template-columns: auto auto auto;
  align-items: center;
  gap: var(--space-4);
  color: var(--slate);
  font-size: var(--text-small);
  text-align: right;
}

.review-summary-row__chevron {
  display: grid;
  width: 1.75rem;
  height: 1.75rem;
  place-items: center;
  border: 1px solid var(--divider);
  border-radius: 50%;
  color: var(--graphite);
  font-size: 1.2rem;
}

@media (max-width: 48rem) {
  .review-summary-row__button {
    align-items: flex-start;
    flex-direction: column;
  }

  .review-summary-row__facts {
    width: 100%;
    text-align: left;
  }
}
</style>
