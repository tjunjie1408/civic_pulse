<script setup lang="ts">
import { computed } from "vue"

import type { ReviewDetail } from "../domain/review"
import { projectNeutralEvidencePoints } from "../domain/neutral-evidence-map"

const props = defineProps<{ readonly detail: ReviewDetail }>()
const projection = computed(() => projectNeutralEvidencePoints(props.detail))
const firstPoint = computed(() => projection.value.points[0])
const secondPoint = computed(() => projection.value.points[1])
const connection = computed(() => {
  const dx = secondPoint.value.x - firstPoint.value.x
  const dy = secondPoint.value.y - firstPoint.value.y
  return {
    left: `${firstPoint.value.x}%`,
    top: `${firstPoint.value.y}%`,
    width: `${Math.sqrt(dx * dx + dy * dy)}%`,
    transform: `rotate(${Math.atan2(dy, dx) * (180 / Math.PI)}deg)`,
  }
})
</script>

<template>
  <section
    class="review-evidence-map"
    role="img"
    aria-label="Neutral evidence map showing the two complaint locations and their relationship"
    data-review-evidence-map
  >
    <div
      class="review-evidence-map__grid"
      aria-hidden="true"
    />
    <div
      class="review-evidence-map__connection"
      :style="connection"
      aria-hidden="true"
    />
    <div
      v-for="point in projection.points"
      :key="point.key"
      class="review-evidence-map__point"
      :style="{ left: `${point.x}%`, top: `${point.y}%` }"
      :data-review-evidence-point="point.key"
    >
      <span
        class="review-evidence-map__marker"
        aria-hidden="true"
      >{{ point.key.toUpperCase() }}</span>
      <span class="review-evidence-map__label">{{ point.label }}</span>
    </div>
    <p class="review-evidence-map__caption">
      Neutral evidence map · relationship under review
    </p>
  </section>
</template>

<style scoped>
.review-evidence-map {
  position: relative;
  min-height: 15rem;
  overflow: hidden;
  border: 1px solid var(--divider);
  background: #f7f9fa;
}

.review-evidence-map__grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgb(207 215 221 / 45%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(207 215 221 / 45%) 1px, transparent 1px);
  background-size: 25% 25%;
}

.review-evidence-map__connection {
  position: absolute;
  height: 2px;
  transform-origin: 0 50%;
  background: var(--civic-blue);
  opacity: 0.65;
}

.review-evidence-map__point {
  position: absolute;
  display: grid;
  justify-items: center;
  gap: var(--space-1);
  transform: translate(-50%, -50%);
}

.review-evidence-map__marker {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border: 2px solid var(--civic-blue);
  border-radius: 50%;
  background: var(--paper-white);
  color: var(--civic-blue);
  font-size: var(--text-small);
  font-weight: 700;
}

.review-evidence-map__label,
.review-evidence-map__caption {
  color: var(--graphite);
  font-size: var(--text-label);
  font-weight: 700;
}

.review-evidence-map__caption {
  position: absolute;
  right: var(--space-3);
  bottom: var(--space-3);
  margin: 0;
  color: var(--slate);
  font-weight: 500;
}
</style>
