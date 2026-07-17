<script setup lang="ts">
import { computed, onMounted } from "vue"

import type { IncidentMapRenderer } from "../application/incident-map-port"
import type { LoadIncidentQueue } from "../application/load-incident-queue"
import type { IncidentPage } from "../domain/incident"
import IncidentMapPanel from "./IncidentMapPanel.vue"
import IncidentQueueRow from "./IncidentQueueRow.vue"
import { useIncidentQueue } from "./use-incident-queue"

const props = defineProps<{
  readonly loadIncidentQueue: Pick<LoadIncidentQueue, "execute">
  readonly createIncidentMapRenderer?: () => IncidentMapRenderer
}>()

const queue = useIncidentQueue(props.loadIncidentQueue)

const currentPage = computed<IncidentPage | null>(() => {
  switch (queue.state.value.kind) {
    case "ready":
    case "empty":
      return queue.state.value.page
    case "loading":
    case "failed":
      return queue.state.value.previous
  }
})

const incidents = computed(() => currentPage.value?.items ?? [])
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
  if (page === null) {
    return "Current result count unavailable"
  }
  if (page.total > page.items.length) {
    return `Showing ${page.items.length} of ${page.total}`
  }
  return `${page.items.length} incident${page.items.length === 1 ? "" : "s"}`
})

onMounted(() => {
  void queue.load()
})
</script>

<template>
  <section
    class="incident-queue"
    aria-labelledby="incident-queue-heading"
    :aria-busy="isLoading"
  >
    <header class="incident-queue__header">
      <div>
        <p class="incident-queue__eyebrow">
          Incident operations
        </p>
        <h1 id="incident-queue-heading">
          Active incident queue
        </h1>
      </div>
      <div class="incident-queue__controls">
        <p
          class="incident-queue__result-count"
          aria-live="polite"
        >
          {{ resultSummary }}
        </p>
        <button
          v-if="!isLoading && !hasInitialFailure"
          class="incident-queue__refresh"
          type="button"
          aria-label="Refresh incidents"
          @click="queue.refresh"
        >
          Refresh
        </button>
      </div>
    </header>

    <div class="incident-queue__workspace">
      <div class="incident-queue__queue-column">
        <p
          v-if="isLoading && currentPage === null"
          class="incident-queue__loading"
          role="status"
        >
          Loading incidents…
        </p>

        <p
          v-if="isEmpty"
          class="incident-queue__empty"
          role="status"
        >
          No active incidents reported.
        </p>

        <div
          v-if="hasInitialFailure"
          class="incident-queue__failure"
          role="alert"
        >
          <p>Unable to load incidents right now.</p>
          <button
            type="button"
            @click="queue.retry"
          >
            Retry
          </button>
        </div>

        <div
          v-if="hasRefreshFailure"
          class="incident-queue__failure"
          role="alert"
        >
          <p>Could not refresh incidents. Showing last known incidents.</p>
          <button
            type="button"
            @click="queue.retry"
          >
            Retry
          </button>
        </div>

        <ol
          v-if="incidents.length > 0"
          class="incident-queue__list"
          aria-label="Active incidents"
        >
          <IncidentQueueRow
            v-for="incident in incidents"
            :key="incident.incidentId"
            :incident="incident"
          />
        </ol>
      </div>

      <IncidentMapPanel
        v-if="createIncidentMapRenderer !== undefined"
        :incidents="incidents"
        :create-renderer="createIncidentMapRenderer"
      />
    </div>
  </section>
</template>

<style scoped>
.incident-queue__header,
.incident-queue__controls,
.incident-queue__failure {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.incident-queue__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.incident-queue__workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(22rem, 0.8fr);
  min-width: 0;
}

.incident-queue__queue-column {
  min-width: 0;
  border-right: 1px solid var(--divider);
}

@media (max-width: 64rem) {
  .incident-queue__workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .incident-queue__queue-column {
    border-right: 0;
    border-bottom: 1px solid var(--divider);
  }
}
</style>
