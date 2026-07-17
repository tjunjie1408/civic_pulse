<script setup lang="ts">
import type { LoadIncidentQueue } from "./features/incidents/application/load-incident-queue"
import type { IncidentMapRenderer } from "./features/incidents/application/incident-map-port"
import IncidentQueuePage from "./features/incidents/ui/IncidentQueuePage.vue"

defineProps<{
  readonly loadIncidentQueue: Pick<LoadIncidentQueue, "execute">
  readonly createIncidentMapRenderer?: () => IncidentMapRenderer
}>()
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
      :load-incident-queue="loadIncidentQueue"
      :create-incident-map-renderer="createIncidentMapRenderer"
    />
  </main>
</template>
