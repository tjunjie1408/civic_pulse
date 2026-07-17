<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue"

import type { SubmitComplaint } from "../application/submit-complaint"
import type { UploadPhoto } from "../application/upload-photo"
import type { IncidentCategory } from "../../incidents/domain/incident"
import { extractPhotoGps, validatePhoto } from "../domain/photo"
import { useComplaintSubmission } from "./use-complaint-submission"

const props = defineProps<{
  readonly submitComplaint: Pick<SubmitComplaint, "execute">
  readonly uploadPhoto: Pick<UploadPhoto, "execute">
}>()

type PhotoUploadState =
  | { readonly kind: "none" }
  | { readonly kind: "uploading" }
  | { readonly kind: "uploaded"; readonly photoId: string }
  | { readonly kind: "failed"; readonly message: string }

const categoryOptions: readonly { readonly value: IncidentCategory; readonly label: string }[] = [
  { value: "pothole", label: "Pothole / road surface" },
  { value: "blocked_drain", label: "Blocked drain" },
  { value: "flooding", label: "Flooding" },
  { value: "rubbish", label: "Rubbish" },
  { value: "street_light", label: "Street light" },
  { value: "other", label: "Other" },
]

const text = ref("")
const category = ref<IncidentCategory | "">("")
const latitude = ref("")
const longitude = ref("")
const selectedFile = ref<File | null>(null)
const photoPreviewUrl = ref<string | null>(null)
const photoError = ref<string | null>(null)
const photoUpload = ref<PhotoUploadState>({ kind: "none" })
const formError = ref<string | null>(null)
const gpsFromPhoto = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const submission = useComplaintSubmission(props.submitComplaint)
const state = computed(() => submission.state.value)
let uploadController: AbortController | null = null

function uploadErrorMessage(kind: string): string {
  switch (kind) {
    case "network":
      return "The photo could not be uploaded because the API is unreachable. Remove it or try again."
    case "unsupported":
      return "The API rejected this file; use a JPEG or PNG photo."
    case "too_large":
      return "The API rejected this photo; keep it under 8 MB."
    default:
      return "The photo could not be uploaded. Remove it or try again."
  }
}

async function startUpload(file: File): Promise<void> {
  uploadController?.abort()
  const controller = new AbortController()
  uploadController = controller
  photoUpload.value = { kind: "uploading" }
  const result = await props.uploadPhoto.execute(file, controller.signal)
  if (controller.signal.aborted || selectedFile.value !== file) return
  uploadController = null
  photoUpload.value = result.ok
    ? { kind: "uploaded", photoId: result.photoId }
    : result.error.kind === "aborted"
      ? { kind: "none" }
      : { kind: "failed", message: uploadErrorMessage(result.error.kind) }
}

function retryUpload(): void {
  if (selectedFile.value !== null) void startUpload(selectedFile.value)
}

function clearPhoto(): void {
  uploadController?.abort()
  uploadController = null
  photoUpload.value = { kind: "none" }
  if (photoPreviewUrl.value !== null) URL.revokeObjectURL(photoPreviewUrl.value)
  selectedFile.value = null
  photoPreviewUrl.value = null
  photoError.value = null
  gpsFromPhoto.value = false
  if (fileInput.value !== null) fileInput.value.value = ""
}

async function onPhotoChange(event: Event): Promise<void> {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) return
  const file = input.files?.[0]
  clearPhoto()
  if (file === undefined) return
  const validation = validatePhoto(file)
  if (!validation.ok) {
    photoError.value = validation.error ?? "That photo cannot be used."
    return
  }
  selectedFile.value = file
  photoPreviewUrl.value = URL.createObjectURL(file)
  void startUpload(file)
  const gps = await extractPhotoGps(file)
  if (selectedFile.value !== file || gps === null) return
  latitude.value = gps.latitude.toFixed(5)
  longitude.value = gps.longitude.toFixed(5)
  gpsFromPhoto.value = true
}

function validateForm(): boolean {
  const numericLatitude = Number(latitude.value)
  const numericLongitude = Number(longitude.value)
  formError.value = null
  if (text.value.trim().length < 3) {
    formError.value = "Describe the civic issue in at least three characters."
    return false
  }
  if (!Number.isFinite(numericLatitude) || numericLatitude < -90 || numericLatitude > 90) {
    formError.value = "Enter a latitude between -90 and 90."
    return false
  }
  if (!Number.isFinite(numericLongitude) || numericLongitude < -180 || numericLongitude > 180) {
    formError.value = "Enter a longitude between -180 and 180."
    return false
  }
  return true
}

function submit(): void {
  if (!validateForm()) return
  if (photoUpload.value.kind === "uploading") {
    formError.value = "Wait for the photo upload to finish, or remove the photo."
    return
  }
  if (photoUpload.value.kind === "failed") {
    formError.value = "Retry or remove the failed photo upload before submitting."
    return
  }
  void submission.submit({
    text: text.value.trim(),
    latitude: Number(latitude.value),
    longitude: Number(longitude.value),
    reportedAt: new Date().toISOString(),
    category: category.value === "" ? null : category.value,
    photoId: photoUpload.value.kind === "uploaded" ? photoUpload.value.photoId : null,
  })
}

function errorMessage(kind: string): string {
  switch (kind) {
    case "network":
      return "The API could not be reached. Your draft is preserved; retry when it is available."
    case "conflict":
      return "This submission was not accepted because its idempotency key conflicts with an earlier request."
    case "contract":
      return "The API returned an unexpected submission response."
    case "service":
      return "The API could not save this complaint. Your draft is preserved."
    default:
      return "The complaint could not be submitted."
  }
}

function resetForm(): void {
  submission.reset()
  text.value = ""
  category.value = ""
  latitude.value = ""
  longitude.value = ""
  clearPhoto()
  formError.value = null
}

onBeforeUnmount(clearPhoto)
</script>

<template>
  <section
    class="submit-page"
    aria-labelledby="submit-page-heading"
  >
    <header class="submit-page__header">
      <div>
        <p class="submit-page__eyebrow">
          Field intake
        </p>
        <h1 id="submit-page-heading">
          Submit a civic report
        </h1>
        <p class="submit-page__description">
          Add a text report, location, and optional photo evidence. Photos upload to the local CivicPulse server.
        </p>
      </div>
    </header>

    <form
      class="submit-page__form"
      @submit.prevent="submit"
    >
      <label class="submit-page__field submit-page__field--wide">
        Issue description
        <textarea
          v-model="text"
          rows="4"
          required
          placeholder="Example: blocked drain beside the market entrance"
        />
      </label>
      <label class="submit-page__field">
        Category <span class="submit-page__optional">(optional)</span>
        <select v-model="category">
          <option value="">Choose a category</option>
          <option
            v-for="option in categoryOptions"
            :key="option.value"
            :value="option.value"
          >{{ option.label }}</option>
        </select>
      </label>
      <label class="submit-page__field">
        Latitude
        <input
          v-model="latitude"
          type="number"
          step="any"
          min="-90"
          max="90"
          required
          placeholder="3.07000"
        >
      </label>
      <label class="submit-page__field">
        Longitude
        <input
          v-model="longitude"
          type="number"
          step="any"
          min="-180"
          max="180"
          required
          placeholder="101.52000"
        >
      </label>

      <div class="submit-page__photo submit-page__field--wide">
        <label for="report-photo">Photo evidence <span class="submit-page__optional">(optional)</span></label>
        <input
          id="report-photo"
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png"
          @change="onPhotoChange"
        >
        <p class="submit-page__help">
          JPEG or PNG, up to 8 MB. The photo is stored with the report and appears in the incident detail.
        </p>
        <p
          v-if="photoError"
          class="submit-page__error"
          role="alert"
        >
          {{ photoError }}
        </p>
        <div
          v-if="photoPreviewUrl !== null"
          class="submit-page__preview"
        >
          <img
            :src="photoPreviewUrl"
            alt="Selected report photo preview"
            data-photo-preview
          >
          <div>
            <p>{{ selectedFile?.name }}</p>
            <p
              v-if="photoUpload.kind === 'uploading'"
              class="submit-page__help"
              role="status"
            >
              Uploading photo…
            </p>
            <p
              v-else-if="photoUpload.kind === 'uploaded'"
              class="submit-page__help"
            >
              Photo uploaded and ready to attach.
            </p>
            <p
              v-else-if="photoUpload.kind === 'failed'"
              class="submit-page__error"
              role="alert"
            >
              {{ photoUpload.message }}
            </p>
            <button
              v-if="photoUpload.kind === 'failed'"
              type="button"
              @click="retryUpload"
            >
              Retry upload
            </button>
            <p
              v-if="gpsFromPhoto"
              class="submit-page__help"
            >
              Coordinates filled from photo GPS metadata.
            </p>
            <button
              type="button"
              @click="clearPhoto"
            >
              Remove photo
            </button>
          </div>
        </div>
      </div>

      <p
        v-if="formError"
        class="submit-page__error submit-page__field--wide"
        role="alert"
      >
        {{ formError }}
      </p>
      <p
        v-if="state.kind === 'failed'"
        class="submit-page__error submit-page__field--wide"
        role="alert"
      >
        {{ errorMessage(state.error.kind) }}
      </p>

      <div class="submit-page__actions submit-page__field--wide">
        <button
          type="submit"
          :disabled="state.kind === 'submitting' || photoUpload.kind === 'uploading'"
        >
          {{ state.kind === "submitting" ? "Submitting…" : photoUpload.kind === "uploading" ? "Waiting for photo upload…" : "Submit report" }}
        </button>
        <button
          v-if="state.kind === 'failed'"
          type="button"
          @click="submission.retry"
        >
          Retry submission
        </button>
      </div>
    </form>

    <section
      v-if="state.kind === 'succeeded'"
      class="submit-page__result"
      aria-live="polite"
      data-submission-result
    >
      <div>
        <p class="submit-page__eyebrow">
          Submission result
        </p>
        <h2>{{ state.submission.created ? "Report saved" : "Existing report replayed" }}</h2>
        <p>Complaint {{ state.submission.complaint.complaintId }} was accepted by the API.</p>
        <p
          v-if="state.submission.complaint.photoPath"
          class="submit-page__help"
        >
          Photo stored as {{ state.submission.complaint.photoPath }}. It will appear in the incident detail.
        </p>
      </div>
      <dl class="submit-page__result-facts">
        <div><dt>Previous snapshots</dt><dd>{{ state.submission.incidentTransition.previousIncidentSnapshotIds.length || "None" }}</dd></div>
        <div><dt>Current snapshots</dt><dd>{{ state.submission.incidentTransition.currentIncidentSnapshotIds.length || "None" }}</dd></div>
        <div><dt>Relationship decisions</dt><dd>{{ state.submission.relationshipDecisions.length }}</dd></div>
        <div><dt>Incidents returned</dt><dd>{{ state.submission.incidents.length }}</dd></div>
      </dl>
      <button
        type="button"
        @click="resetForm"
      >
        Submit another report
      </button>
    </section>
  </section>
</template>

<style scoped>
.submit-page {
  overflow: hidden;
  border: 1px solid var(--divider);
  background: var(--paper-white);
}

.submit-page__header {
  padding: var(--space-5) clamp(var(--space-4), 3vw, var(--space-6));
  border-bottom: 1px solid var(--divider);
}

.submit-page__eyebrow {
  margin: 0 0 var(--space-2);
  color: var(--slate);
  font-size: var(--text-label);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.submit-page h1,
.submit-page h2 {
  margin: 0;
  line-height: var(--leading-tight);
}

.submit-page__description,
.submit-page__help {
  max-width: 48rem;
  margin: var(--space-2) 0 0;
  color: var(--slate);
  font-size: var(--text-small);
}

.submit-page__form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  padding: var(--space-5) clamp(var(--space-4), 3vw, var(--space-6));
}

.submit-page__field,
.submit-page__photo {
  display: grid;
  align-content: start;
  gap: var(--space-1);
  color: var(--slate);
  font-size: var(--text-small);
  font-weight: 600;
}

.submit-page__field--wide {
  grid-column: 1 / -1;
}

.submit-page textarea,
.submit-page input,
.submit-page select {
  width: 100%;
  min-height: 2.4rem;
  padding: 0.55rem;
  border: 1px solid var(--divider);
  border-radius: 2px;
  background: var(--paper-white);
  color: var(--graphite);
}

.submit-page textarea {
  min-height: 7rem;
  resize: vertical;
}

.submit-page__optional {
  font-weight: 400;
}

.submit-page__photo > input {
  padding: 0.4rem;
}

.submit-page__preview {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--divider);
  background: #f7f9fa;
}

.submit-page__preview img {
  width: min(14rem, 100%);
  max-height: 14rem;
  object-fit: contain;
  background: var(--paper-white);
}

.submit-page__preview p {
  margin: 0;
  color: var(--graphite);
}

.submit-page__preview button,
.submit-page__actions button,
.submit-page__result button {
  min-height: 2.35rem;
  margin-top: var(--space-3);
  padding: 0.45rem 0.8rem;
  border: 1px solid var(--civic-blue);
  border-radius: 2px;
  background: var(--paper-white);
  color: var(--civic-blue);
  cursor: pointer;
  font-weight: 700;
}

.submit-page__actions {
  display: flex;
  gap: var(--space-3);
}

.submit-page__actions button[type="submit"] {
  background: var(--civic-blue);
  color: var(--paper-white);
}

.submit-page button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.submit-page__error {
  margin: 0;
  color: var(--oxblood);
  font-size: var(--text-small);
}

.submit-page__result {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(14rem, 0.6fr);
  gap: var(--space-5);
  padding: var(--space-5) clamp(var(--space-4), 3vw, var(--space-6));
  border-top: 1px solid var(--divider);
  background: #f0f7f3;
}

.submit-page__result-facts {
  display: grid;
  gap: var(--space-2);
  margin: 0;
}

.submit-page__result-facts div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}

.submit-page__result-facts dt {
  color: var(--slate);
  font-size: var(--text-label);
  text-transform: uppercase;
}

.submit-page__result-facts dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 48rem) {
  .submit-page__form,
  .submit-page__result {
    grid-template-columns: minmax(0, 1fr);
  }

  .submit-page__preview {
    flex-direction: column;
  }
}
</style>
