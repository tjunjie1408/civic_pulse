<script setup lang="ts">
import { computed } from "vue"

import type {
  IncidentCategory,
  IncidentStatus,
  IncidentSummary,
  OperationalPriorityLevel,
} from "../domain/incident"
import type { IncidentDetail } from "../domain/incident"

const props = defineProps<{
  readonly incident: IncidentSummary
  readonly selected?: boolean
  readonly hovered?: boolean
  readonly expanded?: boolean
  readonly detail?: IncidentDetail | null
  readonly detailState?: "idle" | "loading" | "ready" | "missing" | "failed"
}>()

const emit = defineEmits<{
  (event: "select", incidentId: string): void
  (event: "preview", incidentId: string | null): void
  (event: "open-detail", incidentId: string): void
}>()

function selectIncident(): void {
  emit("select", props.incident.incidentId)
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault()
    selectIncident()
  }
}

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
    <article
      class="incident-queue-row__ledger-entry"
      :class="{
        'incident-queue-row--selected': props.selected === true,
        'incident-queue-row--hovered': props.hovered === true,
        'incident-queue-row--expanded': props.expanded === true,
      }"
      :data-incident-id="incident.incidentId"
      role="button"
      tabindex="0"
      :aria-pressed="props.selected === true"
      @click="selectIncident"
      @keydown="handleKeydown"
      @mouseenter="emit('preview', incident.incidentId)"
      @mouseleave="emit('preview', null)"
      @focus="emit('preview', incident.incidentId)"
      @blur="emit('preview', null)"
    >
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

    <section
      v-if="props.expanded"
      class="incident-queue-row__detail"
      data-incident-detail
      :aria-labelledby="`incident-detail-heading-${incident.incidentId}`"
    >
      <h3 :id="`incident-detail-heading-${incident.incidentId}`">
        Confirmed evidence preview
      </h3>

      <p
        v-if="props.detailState === 'loading' || props.detailState === 'idle'"
        class="incident-queue-row__detail-status"
        role="status"
      >
        Loading confirmed reports…
      </p>
      <p
        v-else-if="props.detailState === 'missing'"
        class="incident-queue-row__detail-status"
        role="status"
      >
        Confirmed evidence is no longer available for this snapshot.
      </p>
      <p
        v-else-if="props.detailState === 'failed'"
        class="incident-queue-row__detail-status"
        role="status"
      >
        Unable to load confirmed reports for this snapshot.
      </p>

      <template v-else-if="props.detail !== null && props.detail !== undefined">
        <p data-confirmed-report-count>
          Showing {{ props.detail.confirmedReports.items.length }} of
          {{ props.detail.confirmedReports.total }} confirmed reports.
        </p>
        <ul
          class="incident-queue-row__reports"
          aria-label="Confirmed report preview"
        >
          <li
            v-for="report in props.detail.confirmedReports.items"
            :key="report.complaintId"
            class="incident-queue-row__report"
          >
            <p>{{ report.text }}</p>
            <small>
              {{ report.category }} · {{ report.latitude.toFixed(4) }}, {{ report.longitude.toFixed(4) }} ·
              {{ report.photoAvailable ? "Photo attached" : "No photo attached" }}
            </small>
          </li>
        </ul>
        <p
          v-if="props.detail.confirmedReports.hasMore"
          data-confirmed-report-more
          class="incident-queue-row__detail-status"
        >
          More reports are available in the full incident.
        </p>
        <button
          type="button"
          data-open-full-incident
          @click.stop="emit('open-detail', incident.incidentId)"
        >
          Open full incident
        </button>
      </template>
    </section>
  </li>
</template>
