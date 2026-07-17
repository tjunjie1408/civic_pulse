<script setup lang="ts">
import type { LoadIncidentQueue } from "./features/incidents/application/load-incident-queue"
import type { IncidentMapRenderer } from "./features/incidents/application/incident-map-port"
import type { LoadIncidentDetail } from "./features/incidents/application/load-incident-detail"
import IncidentQueuePage from "./features/incidents/ui/IncidentQueuePage.vue"
import IncidentDetailPage from "./features/incidents/ui/IncidentDetailPage.vue"
import { useAppRoute } from "./routing/app-route"

const props = defineProps<{
  readonly loadIncidentQueue: Pick<LoadIncidentQueue, "execute">
  readonly loadIncidentDetail: Pick<LoadIncidentDetail, "execute">
  readonly createIncidentMapRenderer?: () => IncidentMapRenderer
}>()

const { route, notice, openIncident, returnToQueue } = useAppRoute()

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
    <IncidentDetailPage
      v-else
      :snapshot-id="route.snapshotId"
      :load-incident-detail="props.loadIncidentDetail"
      @back="returnToQueue"
      @stale="handleStaleIncident"
    />
  </main>
</template>
