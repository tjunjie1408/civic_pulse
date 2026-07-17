import type { IncidentCategory } from "../../../incidents/domain/incident"
import type { components } from "../../../incidents/adapters/http/generated/openapi"
import type {
  ReviewAffectedIncident,
  ReviewComplaint,
  ReviewDecisionSource,
  ReviewDetail,
  ReviewLocationCompatibility,
  ReviewLocationEntity,
  ReviewLocationEntityKind,
  ReviewMatchState,
  ReviewMatcherEvidence,
  ReviewMutation,
  ReviewPage,
  ReviewPriority,
  ReviewStatus,
  ReviewSummary,
} from "../../domain/review"

type ReviewSummaryTransport = components["schemas"]["ReviewSummaryResponse"]
type ReviewListTransport = components["schemas"]["ReviewListResponse"]
type ReviewDetailTransport = components["schemas"]["ReviewDetailResponse"]
type ReviewMutationTransport = components["schemas"]["ReviewMutationResponse"]
type ComplaintTransport = ReviewDetailTransport["complaint_a"]
type EvidenceTransport = NonNullable<ReviewDetailTransport["matcher_evidence"]>
type EntityTransport = EvidenceTransport["first_location_entities"][number]
type AffectedIncidentTransport = ReviewMutationTransport["affected_incidents"][number]

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ISO_DATE_TIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})[Tt](?:[01]\d|2[0-3]):[0-5]\d:(?:[0-5]\d|60)(?:\.\d+)?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/

const SUMMARY_KEYS = [
  "review_id",
  "left_complaint_id",
  "right_complaint_id",
  "original_matcher_recommendation",
  "matcher_reasons",
  "status",
  "created_at",
  "resolved_at",
  "reviewer_id",
  "review_note",
  "final_relationship_state",
  "decision_source",
  "graph_version",
] as const satisfies readonly (keyof ReviewSummaryTransport)[]
const LIST_KEYS = ["items", "limit", "offset", "total"] as const satisfies readonly (
  keyof ReviewListTransport
)[]
const COMPLAINT_KEYS = [
  "complaint_id",
  "text",
  "category",
  "latitude",
  "longitude",
  "reported_at",
  "photo_path",
] as const satisfies readonly (keyof ComplaintTransport)[]
const ENTITY_KEYS = ["kind", "value", "raw"] as const satisfies readonly (keyof EntityTransport)[]
const EVIDENCE_KEYS = [
  "semantic_similarity",
  "geo_distance_metres",
  "time_difference_seconds",
  "category_compatibility",
  "location_compatibility",
  "first_location_entities",
  "second_location_entities",
] as const satisfies readonly (keyof EvidenceTransport)[]
const DETAIL_KEYS = [
  "review_id",
  "status",
  "complaint_a",
  "complaint_b",
  "original_matcher_recommendation",
  "matcher_reasons",
  "matcher_evidence",
  "created_at",
  "resolved_at",
  "reviewer_id",
  "review_note",
  "final_relationship_state",
  "decision_source",
  "graph_version",
  "previous_incident_snapshot_ids",
  "new_incident_snapshot_ids",
] as const satisfies readonly (keyof ReviewDetailTransport)[]
const INCIDENT_KEYS = [
  "incident_id",
  "status",
  "category_summary",
  "priority",
  "confirmed_report_count",
  "pending_candidate_count",
  "centroid",
  "radius_metres",
  "earliest_reported_at",
  "latest_reported_at",
  "conflict_reasons",
] as const satisfies readonly (keyof AffectedIncidentTransport)[]
const CENTROID_KEYS = ["latitude", "longitude"] as const
const PRIORITY_KEYS = ["level", "reasons", "policy_version"] as const satisfies readonly (
  keyof NonNullable<AffectedIncidentTransport["priority"]>
)[]
const MUTATION_KEYS = [
  "review",
  "final_relationship_state",
  "affected_complaint_ids",
  "previous_incident_snapshot_ids",
  "new_incident_snapshot_ids",
  "affected_incidents",
  "resulting_priorities",
  "conflict_status",
] as const satisfies readonly (keyof ReviewMutationTransport)[]

function invalidResponse(): never {
  throw new TypeError("Invalid review response")
}

function hasExactKeys(
  value: unknown,
  expectedKeys: readonly string[],
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Reflect.ownKeys(value).length === expectedKeys.length &&
    expectedKeys.every((key) => Object.hasOwn(value, key))
  )
}

function isDenseArray(value: unknown): value is unknown[] {
  if (!Array.isArray(value)) return false
  for (let index = 0; index < value.length; index += 1) {
    if (!Object.hasOwn(value, index)) return false
  }
  return true
}

function requireString(value: unknown): string {
  if (typeof value !== "string") return invalidResponse()
  return value
}

function requireNullableString(value: unknown): string | null {
  if (value === null) return null
  return requireString(value)
}

function requireFiniteNumber(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return invalidResponse()
  return value
}

function requireCount(value: unknown): number {
  const count = requireFiniteNumber(value)
  if (!Number.isInteger(count) || count < 0) return invalidResponse()
  return count
}

function requireUuid(value: unknown): string {
  const uuid = requireString(value)
  if (!UUID_PATTERN.test(uuid)) return invalidResponse()
  return uuid
}

function requireDateTime(value: unknown): string {
  const dateTime = requireString(value)
  if (!ISO_DATE_TIME_PATTERN.test(dateTime)) return invalidResponse()
  return dateTime
}

function decodeStringArray(value: unknown): readonly string[] {
  if (!isDenseArray(value)) return invalidResponse()
  return value.map(requireString)
}

function decodeUuidArray(value: unknown): readonly string[] {
  if (!isDenseArray(value)) return invalidResponse()
  return value.map(requireUuid)
}

function decodeCategory(value: unknown): IncidentCategory {
  switch (value) {
    case "pothole":
    case "blocked_drain":
    case "flooding":
    case "rubbish":
    case "street_light":
    case "other":
      return value
    default:
      return invalidResponse()
  }
}

function decodeCategories(value: unknown): readonly IncidentCategory[] {
  if (!isDenseArray(value)) return invalidResponse()
  return value.map(decodeCategory)
}

function decodeStatus(value: unknown): "confirmed" | "isolated" | "conflict" {
  switch (value) {
    case "confirmed":
    case "isolated":
    case "conflict":
      return value
    default:
      return invalidResponse()
  }
}

function decodeReviewStatus(value: unknown): ReviewStatus {
  switch (value) {
    case "pending":
    case "approved":
    case "rejected":
      return value
    default:
      return invalidResponse()
  }
}

function decodeMatchState(value: unknown): ReviewMatchState {
  switch (value) {
    case "auto_match":
    case "no_match":
    case "review_required":
      return value
    default:
      return invalidResponse()
  }
}

function decodeDecisionSource(value: unknown): ReviewDecisionSource | null {
  if (value === null) return null
  switch (value) {
    case "automated":
      return "automated"
    case "officer_review":
      return "officer_review"
    default:
      return invalidResponse()
  }
}

function decodeLocationCompatibility(value: unknown): ReviewLocationCompatibility {
  switch (value) {
    case "compatible":
    case "conflicting":
    case "unknown":
      return value
    default:
      return invalidResponse()
  }
}

function decodeLocationKind(value: unknown): ReviewLocationEntityKind {
  switch (value) {
    case "block":
    case "unit":
    case "street":
    case "landmark":
      return value
    default:
      return invalidResponse()
  }
}

function decodeCentroid(value: unknown): Readonly<{ latitude: number; longitude: number }> {
  if (!hasExactKeys(value, CENTROID_KEYS)) return invalidResponse()
  return { latitude: requireFiniteNumber(value.latitude), longitude: requireFiniteNumber(value.longitude) }
}

function decodePriority(value: unknown): ReviewPriority | null {
  if (value === null) return null
  if (!hasExactKeys(value, PRIORITY_KEYS)) return invalidResponse()
  const level = value.level
  if (
    level !== "critical" &&
    level !== "high" &&
    level !== "medium" &&
    level !== "low" &&
    level !== "review_required"
  ) return invalidResponse()
  return {
    level,
    reasons: decodeStringArray(value.reasons),
    policyVersion: requireString(value.policy_version),
  }
}

function decodeComplaint(value: unknown): ReviewComplaint {
  if (!hasExactKeys(value, COMPLAINT_KEYS)) return invalidResponse()
  if (value.photo_path !== null && typeof value.photo_path !== "string") return invalidResponse()
  return {
    complaintId: requireUuid(value.complaint_id),
    text: requireString(value.text),
    category: decodeCategory(value.category),
    latitude: requireFiniteNumber(value.latitude),
    longitude: requireFiniteNumber(value.longitude),
    reportedAt: requireDateTime(value.reported_at),
    photoAvailable: value.photo_path !== null,
  }
}

function decodeEntity(value: unknown): ReviewLocationEntity {
  if (!hasExactKeys(value, ENTITY_KEYS)) return invalidResponse()
  return { kind: decodeLocationKind(value.kind), value: requireString(value.value), raw: requireString(value.raw) }
}

function decodeEntities(value: unknown): readonly ReviewLocationEntity[] {
  if (!isDenseArray(value)) return invalidResponse()
  return value.map(decodeEntity)
}

function decodeEvidence(value: unknown): ReviewMatcherEvidence | null {
  if (value === null) return null
  if (!hasExactKeys(value, EVIDENCE_KEYS)) return invalidResponse()
  if (typeof value.category_compatibility !== "boolean") return invalidResponse()
  return {
    semanticSimilarity: requireFiniteNumber(value.semantic_similarity),
    geoDistanceMetres: requireFiniteNumber(value.geo_distance_metres),
    timeDifferenceSeconds: requireFiniteNumber(value.time_difference_seconds),
    categoryCompatibility: value.category_compatibility,
    locationCompatibility: decodeLocationCompatibility(value.location_compatibility),
    firstLocationEntities: decodeEntities(value.first_location_entities),
    secondLocationEntities: decodeEntities(value.second_location_entities),
  }
}

function decodeSummary(value: unknown): ReviewSummary {
  if (!hasExactKeys(value, SUMMARY_KEYS)) return invalidResponse()
  return {
    reviewId: requireUuid(value.review_id),
    leftComplaintId: requireUuid(value.left_complaint_id),
    rightComplaintId: requireUuid(value.right_complaint_id),
    originalMatcherRecommendation: decodeMatchState(value.original_matcher_recommendation),
    matcherReasons: decodeStringArray(value.matcher_reasons),
    status: decodeReviewStatus(value.status),
    createdAt: requireDateTime(value.created_at),
    resolvedAt: requireNullableString(value.resolved_at),
    reviewerId: requireNullableString(value.reviewer_id),
    reviewNote: requireNullableString(value.review_note),
    finalRelationshipState:
      value.final_relationship_state === null ? null : decodeMatchState(value.final_relationship_state),
    decisionSource: decodeDecisionSource(value.decision_source),
    graphVersion: requireString(value.graph_version),
  }
}

export function decodeReviewList(value: unknown): ReviewPage {
  if (!hasExactKeys(value, LIST_KEYS) || !isDenseArray(value.items)) return invalidResponse()
  return {
    items: value.items.map(decodeSummary),
    limit: requireCount(value.limit),
    offset: requireCount(value.offset),
    total: requireCount(value.total),
  }
}

export function decodeReviewDetail(value: unknown): ReviewDetail {
  if (!hasExactKeys(value, DETAIL_KEYS)) return invalidResponse()
  return {
    reviewId: requireUuid(value.review_id),
    status: decodeReviewStatus(value.status),
    complaintA: decodeComplaint(value.complaint_a),
    complaintB: decodeComplaint(value.complaint_b),
    originalMatcherRecommendation: decodeMatchState(value.original_matcher_recommendation),
    matcherReasons: decodeStringArray(value.matcher_reasons),
    matcherEvidence: decodeEvidence(value.matcher_evidence),
    createdAt: requireDateTime(value.created_at),
    resolvedAt: requireNullableString(value.resolved_at),
    reviewerId: requireNullableString(value.reviewer_id),
    reviewNote: requireNullableString(value.review_note),
    finalRelationshipState:
      value.final_relationship_state === null ? null : decodeMatchState(value.final_relationship_state),
    decisionSource: decodeDecisionSource(value.decision_source),
    graphVersion: requireString(value.graph_version),
    previousIncidentSnapshotIds: decodeUuidArray(value.previous_incident_snapshot_ids),
    newIncidentSnapshotIds: decodeUuidArray(value.new_incident_snapshot_ids),
  }
}

function decodeAffectedIncident(value: unknown): ReviewAffectedIncident {
  if (!hasExactKeys(value, INCIDENT_KEYS)) return invalidResponse()
  return {
    incidentId: requireUuid(value.incident_id),
    status: decodeStatus(value.status),
    categories: decodeCategories(value.category_summary),
    priority: decodePriority(value.priority),
    confirmedReportCount: requireCount(value.confirmed_report_count),
    pendingCandidateCount: requireCount(value.pending_candidate_count),
    centroid: decodeCentroid(value.centroid),
    radiusMetres: requireFiniteNumber(value.radius_metres),
    earliestReportedAt: requireDateTime(value.earliest_reported_at),
    latestReportedAt: requireDateTime(value.latest_reported_at),
    conflictReasons: decodeStringArray(value.conflict_reasons),
  }
}

function decodeAffectedIncidents(value: unknown): readonly ReviewAffectedIncident[] {
  if (!isDenseArray(value)) return invalidResponse()
  return value.map(decodeAffectedIncident)
}

function decodeResultingPriorities(value: unknown): readonly (ReviewPriority | null)[] {
  if (!isDenseArray(value)) return invalidResponse()
  return value.map((item) => decodePriority(item))
}

export function decodeReviewMutation(value: unknown): ReviewMutation {
  if (!hasExactKeys(value, MUTATION_KEYS)) return invalidResponse()
  return {
    review: decodeReviewDetail(value.review),
    finalRelationshipState: decodeMatchState(value.final_relationship_state),
    affectedComplaintIds: decodeUuidArray(value.affected_complaint_ids),
    previousIncidentSnapshotIds: decodeUuidArray(value.previous_incident_snapshot_ids),
    newIncidentSnapshotIds: decodeUuidArray(value.new_incident_snapshot_ids),
    affectedIncidents: decodeAffectedIncidents(value.affected_incidents),
    resultingPriorities: decodeResultingPriorities(value.resulting_priorities),
    conflictStatus: value.conflict_status === null ? null : decodeStatus(value.conflict_status),
  }
}
