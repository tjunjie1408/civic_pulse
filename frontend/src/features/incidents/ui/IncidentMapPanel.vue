<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"

import type {
  IncidentMapRenderer,
  MapLifecycleState,
} from "../application/incident-map-port"
import { buildHeatCells, type HeatmapMode } from "../domain/heatmap"
import type { IncidentCategory, IncidentSummary } from "../domain/incident"

const props = defineProps<{
  readonly incidents: readonly IncidentSummary[]
  readonly createRenderer: () => IncidentMapRenderer
  readonly selectedIncidentId?: string | null
  readonly hoveredIncidentId?: string | null
}>()

const emit = defineEmits<{
  (event: "select", incidentId: string): void
  (event: "preview", incidentId: string | null): void
}>()

const renderer = props.createRenderer()

const CATEGORY_OPTIONS: readonly { readonly value: IncidentCategory; readonly label: string }[] = [
  { value: "flooding", label: "Flooding" },
  { value: "blocked_drain", label: "Blocked drain" },
  { value: "pothole", label: "Pothole / road" },
  { value: "rubbish", label: "Rubbish" },
  { value: "street_light", label: "Street light" },
  { value: "other", label: "Other" },
]


const selectedValue = ref<"all" | IncidentCategory>("all")
const mapContainer = ref<HTMLElement | null>(null)
const rendererMounted = ref(false)
const mapLifecycle = ref<MapLifecycleState>("loading")

let unsubscribeSelect: (() => void) | undefined
let unsubscribePreview: (() => void) | undefined
let unsubscribeLifecycle: (() => void) | undefined

const selectedMode = computed<HeatmapMode>(() =>
  selectedValue.value === "all"
    ? { kind: "all" }
    : { kind: "category", category: selectedValue.value },
)
const cells = computed(() => buildHeatCells(props.incidents, selectedMode.value))
const isEmpty = computed(() => cells.value.length === 0)
const isMapLoading = computed(() => mapLifecycle.value === "loading")
const isMapDegraded = computed(() => mapLifecycle.value === "degraded")
const isMapRecovering = computed(() => mapLifecycle.value === "recovering")
const handleResize = (): void => renderer.resize()

function renderMap(): void {
  if (!rendererMounted.value) {
    return
  }
  renderer.render({
    incidents: props.incidents,
    cells: cells.value,
    mode: selectedMode.value,
    selectedIncidentId: props.selectedIncidentId ?? null,
    hoveredIncidentId: props.hoveredIncidentId ?? null,
  })
}

onMounted(() => {
  if (mapContainer.value === null) {
    return
  }
  unsubscribeSelect = renderer.onIncidentSelect((incidentId) => emit("select", incidentId))
  unsubscribePreview = renderer.onIncidentPreview((incidentId) => emit("preview", incidentId))
  unsubscribeLifecycle = renderer.onLifecycleChange((state) => {
    mapLifecycle.value = state
  })
  renderer.mount(mapContainer.value)
  renderer.resize()
  rendererMounted.value = true
  window.addEventListener("resize", handleResize)
  renderMap()
})

watch(
  [cells, selectedMode, () => props.incidents, () => props.selectedIncidentId, () => props.hoveredIncidentId],
  renderMap,
)

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize)
  unsubscribeSelect?.()
  unsubscribePreview?.()
  unsubscribeLifecycle?.()
  renderer.dispose()
  rendererMounted.value = false
})
</script>

<template>
  <section
    class="incident-map-panel"
    aria-labelledby="incident-map-heading"
  >
    <header class="incident-map-panel__header">
      <div>
        <p class="incident-map-panel__eyebrow">
          Spatial evidence
        </p>
        <h2 id="incident-map-heading">
          Incident map
        </h2>
      </div>
      <label class="incident-map-panel__mode">
        <span>Heatmap category</span>
        <select
          v-model="selectedValue"
          aria-label="Heatmap category"
        >
          <option value="all">All confirmed</option>
          <option
            v-for="category in CATEGORY_OPTIONS"
            :key="category.value"
            :value="category.value"
          >
            {{ category.label }}
          </option>
        </select>
      </label>
    </header>

    <div class="incident-map-panel__map-wrap">
      <div
        ref="mapContainer"
        class="incident-map-panel__map"
        data-map-container
        role="img"
        aria-label="Confirmed incident density map"
        :aria-busy="isMapLoading"
      />
      <div
        class="incident-map-panel__density-legend"
        role="group"
        aria-label="Report density"
      >
        <span>Low</span>
        <span
          class="incident-map-panel__density-gradient"
          data-density-gradient
          aria-hidden="true"
        />
        <span>High</span>
      </div>
      <p
        v-if="isEmpty"
        class="incident-map-panel__empty"
        data-map-empty
        data-map-status
        role="status"
      >
        No confirmed incident density for this view.
      </p>
    </div>


    <div
      v-if="isMapLoading || isMapDegraded || isMapRecovering"
      class="incident-map-panel__notice incident-map-panel__notice--lifecycle"
      data-map-status
      role="status"
    >
      <span
        v-if="isMapLoading"
        data-map-loading
      >Loading street map.</span>
      <span v-else-if="isMapDegraded">Base map unavailable. Incident overlays remain available.</span>
      <span v-else>Restoring base map.</span>
      <button
        v-if="isMapDegraded"
        type="button"
        class="incident-map-panel__retry"
        data-map-retry
        @click="renderer.retry"
      >
        Retry map
      </button>
    </div>
  </section>
</template>
