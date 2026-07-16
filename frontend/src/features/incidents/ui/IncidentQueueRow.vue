<script setup lang="ts">
import { computed } from "vue"

import type {
  IncidentCategory,
  IncidentStatus,
  IncidentSummary,
  OperationalPriorityLevel,
} from "../domain/incident"

const props = defineProps<{
  readonly incident: IncidentSummary
}>()

const categoryLabels: Readonly<Record<IncidentCategory, string>> = {
  pothole: "Pothole / road",
  blocked_drain: "Blocked drain",
  flooding: "Flooding",
  rubbish: "Rubbish",
  street_light: "Street light",
  other: "Other",
}

const priorityLabels: Readonly<Record<OperationalPriorityLevel, string>> = {
  critical: "Critical operational priority",
  high: "High operational priority",
  medium: "Medium operational priority",
  low: "Low operational priority",
}

const statusLabels: Readonly<Record<IncidentStatus, string>> = {
  confirmed: "Confirmed",
  isolated: "Isolated",
  conflict: "Conflict",
}

const categories = computed(() =>
  props.incident.categories.map((category) => categoryLabels[category]).join(" · "),
)
const priority = computed(() =>
  props.incident.priority === null
    ? "No operational priority"
    : priorityLabels[props.incident.priority.level],
)
const status = computed(() => statusLabels[props.incident.status])
const radius = computed(() =>
  new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 }).format(
    props.incident.radiusMetres,
  ),
)
const latestUpdate = computed(() => {
  const value = new Date(props.incident.latestReportedAt)
  const formatted = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(value)
  return `${formatted} UTC`
})
const abbreviatedSnapshotId = computed(() => props.incident.incidentId.slice(0, 8))
</script>

<template>
  <li class="incident-queue-row">
    <article class="incident-queue-row__ledger-entry">
      <header class="incident-queue-row__header">
        <p class="incident-queue-row__priority">
          {{ priority }}
        </p>
        <h2 class="incident-queue-row__categories">
          {{ categories }}
        </h2>
      </header>

      <dl class="incident-queue-row__facts">
        <div class="incident-queue-row__fact">
          <dt>Status</dt>
          <dd>{{ status }}</dd>
        </div>
        <div class="incident-queue-row__fact">
          <dt>Confirmed reports</dt>
          <dd>{{ incident.confirmedReportCount }}</dd>
        </div>
        <div class="incident-queue-row__fact">
          <dt>Pending review candidates</dt>
          <dd>{{ incident.pendingCandidateCount }}</dd>
        </div>
        <div class="incident-queue-row__fact">
          <dt>Affected radius</dt>
          <dd>{{ radius }} m</dd>
        </div>
        <div class="incident-queue-row__fact">
          <dt>Latest update</dt>
          <dd>
            <time :datetime="incident.latestReportedAt">{{ latestUpdate }}</time>
          </dd>
        </div>
      </dl>

      <footer class="incident-queue-row__metadata">
        <small class="incident-queue-row__snapshot">
          Snapshot {{ abbreviatedSnapshotId }}
        </small>
      </footer>
    </article>
  </li>
</template>
