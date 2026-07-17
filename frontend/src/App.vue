<script setup lang="ts">
import type { LoadIncidentQueue } from "./features/incidents/application/load-incident-queue"
import type { IncidentMapRenderer } from "./features/incidents/application/incident-map-port"
import type { LoadIncidentDetail } from "./features/incidents/application/load-incident-detail"
import type { LoadReviewDetail } from "./features/reviews/application/load-review-detail"
import type { LoadReviewQueue } from "./features/reviews/application/load-review-queue"
import type { ResolveReview } from "./features/reviews/application/resolve-review"
import IncidentQueuePage from "./features/incidents/ui/IncidentQueuePage.vue"
import IncidentDetailPage from "./features/incidents/ui/IncidentDetailPage.vue"
import ReviewQueuePage from "./features/reviews/ui/ReviewQueuePage.vue"
import { useAppRoute } from "./routing/app-route"

const props = defineProps<{
  readonly loadIncidentQueue: Pick<LoadIncidentQueue, "execute">
  readonly loadIncidentDetail: Pick<LoadIncidentDetail, "execute">
  readonly loadReviewQueue: Pick<LoadReviewQueue, "execute">
  readonly loadReviewDetail: Pick<LoadReviewDetail, "execute">
  readonly resolveReview: Pick<ResolveReview, "execute">
  readonly createIncidentMapRenderer?: () => IncidentMapRenderer
}>()

const { route, notice, openIncident, openReviews, returnToQueue } = useAppRoute()

function handleStaleIncident(): void {
  returnToQueue(
    "This incident snapshot changed while you were viewing it. Choose a current incident explicitly from the queue; no successor was selected automatically.",
  )
}
</script>

<template>
  <header class="app-shell__header">
    <div class="app-shell__brand">
      <span class="app-shell__wordmark">CivicPulse</span>
      <span class="app-shell__descriptor">Municipal incident ledger</span>
    </div>
    <nav
      class="app-shell__nav"
      aria-label="Primary"
    >
      <button
        type="button"
        :aria-current="route.kind === 'queue' || route.kind === 'incident-detail' ? 'page' : undefined"
        @click="returnToQueue()"
      >
        Incident queue
      </button>
      <button
        type="button"
        :aria-current="route.kind === 'reviews' ? 'page' : undefined"
        @click="openReviews"
      >
        Pending reviews
      </button>
    </nav>
    <h1>Incident operations</h1>
  </header>
  <main class="app-shell__main">
    <IncidentQueuePage
      v-if="route.kind === 'queue'"
      :load-incident-queue="props.loadIncidentQueue"
      :load-incident-detail="props.loadIncidentDetail"
      :create-incident-map-renderer="props.createIncidentMapRenderer"
      :notice="notice"
      @open-detail="openIncident"
    />
    <ReviewQueuePage
      v-else-if="route.kind === 'reviews'"
      :load-review-queue="props.loadReviewQueue"
      :load-review-detail="props.loadReviewDetail"
      :resolve-review="props.resolveReview"
      @back-to-queue="returnToQueue()"
    />
    <IncidentDetailPage
      v-else
      :snapshot-id="route.snapshotId"
      :load-incident-detail="props.loadIncidentDetail"
      @back="returnToQueue"
      @stale="handleStaleIncident"
    />
  </main>
</template>

<style scoped>
.app-shell__nav {
  display: flex;
  gap: var(--space-2);
}

.app-shell__nav button {
  padding: 0.35rem 0.55rem;
  border: 1px solid transparent;
  background: transparent;
  color: var(--slate);
  cursor: pointer;
  font-size: var(--text-small);
  font-weight: 600;
}

.app-shell__nav button[aria-current="page"] {
  border-color: var(--divider);
  background: var(--signal-canvas);
  color: var(--graphite);
}
</style>
