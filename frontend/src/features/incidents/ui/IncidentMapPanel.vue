<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"

import type { IncidentMapRenderer } from "../application/incident-map-port"
import { buildHeatCells, type HeatmapMode } from "../domain/heatmap"
import type { IncidentCategory, IncidentSummary } from "../domain/incident"

const props = defineProps<{
  readonly incidents: readonly IncidentSummary[]
  readonly createRenderer: () => IncidentMapRenderer
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

const CATEGORY_COLORS: Readonly<Record<IncidentCategory, string>> = Object.freeze({
  flooding: "#1677a8",
  blocked_drain: "#267f86",
  pothole: "#a4772d",
  rubbish: "#883f4a",
  street_light: "#5b5b88",
  other: "#64748b",
})

const selectedValue = ref<"all" | IncidentCategory>("all")
const mapContainer = ref<HTMLElement | null>(null)
const rendererMounted = ref(false)
const renderStrategy = ref<"category-heat" | "neutral-density">("neutral-density")

const selectedMode = computed<HeatmapMode>(() =>
  selectedValue.value === "all"
    ? { kind: "all" }
    : { kind: "category", category: selectedValue.value },
)
const cells = computed(() => buildHeatCells(props.incidents, selectedMode.value))
const isEmpty = computed(() => cells.value.length === 0)
const showNeutralFallback = computed(
  () => selectedMode.value.kind === "all" && renderStrategy.value === "neutral-density",
)
const handleResize = (): void => renderer.resize()

function renderMap(): void {
  if (!rendererMounted.value) {
    return
  }
  renderStrategy.value = renderer.render(cells.value, selectedMode.value)
}

onMounted(() => {
  if (mapContainer.value === null) {
    return
  }
  renderer.mount(mapContainer.value)
  rendererMounted.value = true
  window.addEventListener("resize", handleResize)
  renderMap()
})

watch([cells, selectedMode], renderMap)

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize)
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
      />
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

    <p
      v-if="showNeutralFallback"
      class="incident-map-panel__notice"
      data-map-status
      role="status"
    >
      Neutral total-density is shown in All mode. Select a category to see its approved color.
    </p>

    <ul
      class="incident-map-panel__legend"
      aria-label="Incident category colors"
    >
      <li
        v-for="category in CATEGORY_OPTIONS"
        :key="category.value"
        :data-category="category.value"
        :data-color="CATEGORY_COLORS[category.value]"
      >
        <span
          class="incident-map-panel__swatch"
          :style="{ backgroundColor: CATEGORY_COLORS[category.value] }"
          aria-hidden="true"
        />
        <span>{{ category.label }}</span>
      </li>
    </ul>
  </section>
</template>
