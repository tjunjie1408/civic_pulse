<script setup lang="ts">
import { computed, watch } from "vue"

import type { LoadIncidentDetail } from "../application/load-incident-detail"
import { useIncidentDetail } from "./use-incident-detail"

const props = defineProps<{
  readonly snapshotId: string
  readonly loadIncidentDetail: Pick<LoadIncidentDetail, "execute">
}>()

const emit = defineEmits<{
  (event: "back"): void
  (event: "stale", snapshotId: string): void
}>()

const detail = useIncidentDetail(props.loadIncidentDetail)
const detailState = computed(() => detail.state.value)
const readyDetail = computed(() =>
  detailState.value.kind === "ready" ? detailState.value.detail : null,
)

watch(
  () => props.snapshotId,
  (snapshotId) => {
    void detail.load(snapshotId)
  },
  { immediate: true },
)

watch(detail.state, (state) => {
  if (state.kind === "missing") {
    emit("stale", state.incidentId)
  }
})
</script>

<template>
  <section
    class="incident-detail"
    aria-labelledby="incident-detail-heading"
    :aria-busy="detailState.kind === 'loading'"
  >
    <header class="incident-detail__header">
      <button
        type="button"
        data-back-to-queue
        @click="emit('back')"
      >
        Back to incident queue
      </button>
      <p class="incident-detail__eyebrow">
        Membership-derived snapshot
      </p>
      <h1 id="incident-detail-heading">
        Full incident
      </h1>
    </header>

    <p
      v-if="detailState.kind === 'loading'"
      class="incident-detail__status"
      role="status"
    >
      Loading incident evidence…
    </p>

    <div
      v-else-if="detailState.kind === 'failed'"
      class="incident-detail__status"
      role="alert"
    >
      <p>Unable to load this incident snapshot.</p>
      <button
        type="button"
        @click="detail.retry"
      >
        Retry
      </button>
    </div>

    <p
      v-else-if="detailState.kind === 'missing'"
      class="incident-detail__status"
      role="status"
    >
      This incident snapshot is no longer available.
    </p>

    <article
      v-else-if="readyDetail !== null"
      class="incident-detail__body"
      data-incident-detail-ready
    >
      <p class="incident-detail__snapshot">
        Snapshot {{ readyDetail.incidentId.slice(0, 8) }}
      </p>
      <h2>{{ readyDetail.categories.join(" · ") }}</h2>
      <dl class="incident-detail__facts">
        <div>
          <dt>Status</dt>
          <dd>{{ readyDetail.status }}</dd>
        </div>
        <div>
          <dt>Confirmed reports</dt>
          <dd>{{ readyDetail.confirmedReportCount }}</dd>
        </div>
        <div>
          <dt>Pending review candidates</dt>
          <dd>{{ readyDetail.pendingCandidateCount }}</dd>
        </div>
        <div>
          <dt>Affected radius</dt>
          <dd>{{ readyDetail.radiusMetres }} m</dd>
        </div>
      </dl>

      <section
        class="incident-detail__reports"
        aria-labelledby="incident-confirmed-reports-heading"
      >
        <h2 id="incident-confirmed-reports-heading">
          Confirmed reports
        </h2>
        <p>
          Showing {{ readyDetail.confirmedReports.items.length }} of
          {{ readyDetail.confirmedReports.total }} reports.
        </p>
        <ul>
          <li
            v-for="report in readyDetail.confirmedReports.items"
            :key="report.complaintId"
          >
            <p>{{ report.text }}</p>
            <small>
              {{ report.category }} · {{ report.latitude.toFixed(4) }}, {{ report.longitude.toFixed(4) }}
              · {{ report.photoAvailable ? "Photo available" : "No photo available" }}
            </small>
          </li>
        </ul>
        <p v-if="readyDetail.confirmedReports.hasMore">
          More confirmed reports are available in this snapshot.
        </p>
      </section>
    </article>
  </section>
</template>
