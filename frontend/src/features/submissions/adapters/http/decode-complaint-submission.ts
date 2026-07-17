import type {
  IncidentCategory,
  IncidentRelationship,
  IncidentStatus,
  IncidentSummary,
  OperationalPriority,
  OperationalPriorityLevel,
} from "../../../incidents/domain/incident"
import type {
  ComplaintSubmission,
  IncidentTransition,
  SubmittedComplaint,
} from "../../domain/complaint"
import type { components } from "../../../incidents/adapters/http/generated/openapi"

type SubmissionTransport = components["schemas"]["ComplaintSubmissionResponse"]
type ComplaintTransport = SubmissionTransport["complaint"]
type TransitionTransport = SubmissionTransport["incident_transition"]
type IncidentTransport = SubmissionTransport["incidents"][number]
type PriorityTransport = NonNullable<SubmissionTransport["priorities"][number]>
type EdgeTransport = SubmissionTransport["relationship_decisions"][number]

const SUBMISSION_KEYS = [
  "complaint",
  "created",
  "replayed",
  "relationship_decisions",
  "incident_transition",
  "incidents",
  "priorities",
] as const satisfies readonly (keyof SubmissionTransport)[]
const COMPLAINT_KEYS = [
  "complaint_id",
  "text",
  "category",
  "latitude",
  "longitude",
  "reported_at",
  "photo_path",
] as const satisfies readonly (keyof ComplaintTransport)[]
const TRANSITION_KEYS = [
  "previous_incident_snapshot_ids",
  "current_incident_snapshot_ids",
] as const satisfies readonly (keyof TransitionTransport)[]
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
] as const satisfies readonly (keyof IncidentTransport)[]
const CENTROID_KEYS = ["latitude", "longitude"] as const
const PRIORITY_KEYS = ["level", "reasons", "policy_version"] as const satisfies readonly (
  keyof PriorityTransport
)[]
const EDGE_KEYS = [
  "left_id",
  "right_id",
  "decision",
  "reasons",
  "decision_source",
  "matcher_recommendation",
] as const satisfies readonly (keyof EdgeTransport)[]

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ISO_DATE_TIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})[Tt](?:[01]\d|2[0-3]):[0-5]\d:(?:[0-5]\d|60)(?:\.\d+)?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/

function invalidResponse(): never {
  throw new TypeError("Invalid complaint submission response")
}

function hasExactKeys(value: unknown, expected: readonly string[]): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    && Reflect.ownKeys(value).length === expected.length
    && expected.every((key) => Object.hasOwn(value, key))
}

function isDenseArray(value: unknown): value is unknown[] {
  return Array.isArray(value) && value.every((_, index) => Object.hasOwn(value, index))
}

function stringValue(value: unknown): string {
  if (typeof value !== "string") return invalidResponse()
  return value
}

function nullableString(value: unknown): string | null {
  if (value === null) return null
  return stringValue(value)
}

function finiteNumber(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return invalidResponse()
  return value
}

function uuid(value: unknown): string {
  const result = stringValue(value)
  return UUID_PATTERN.test(result) ? result : invalidResponse()
}

function dateTime(value: unknown): string {
  const result = stringValue(value)
  return ISO_DATE_TIME_PATTERN.test(result) ? result : invalidResponse()
}

function strings(value: unknown): readonly string[] {
  if (!isDenseArray(value)) return invalidResponse()
  return value.map(stringValue)
}

function category(value: unknown): IncidentCategory {
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

function status(value: unknown): IncidentStatus {
  switch (value) {
    case "confirmed":
    case "isolated":
    case "conflict":
      return value
    default:
      return invalidResponse()
  }
}

function priorityLevel(value: unknown): OperationalPriorityLevel {
  switch (value) {
    case "critical":
    case "high":
    case "medium":
    case "low":
      return value
    default:
      return invalidResponse()
  }
}

function decodePriority(value: unknown): OperationalPriority | null {
  if (value === null) return null
  if (!hasExactKeys(value, PRIORITY_KEYS)) return invalidResponse()
  return {
    level: priorityLevel(value.level),
    reasons: strings(value.reasons),
    policyVersion: stringValue(value.policy_version),
  }
}

function decodeComplaint(value: unknown): SubmittedComplaint {
  if (!hasExactKeys(value, COMPLAINT_KEYS)) return invalidResponse()
  const photoPath = nullableString(value.photo_path)
  return {
    complaintId: uuid(value.complaint_id),
    text: stringValue(value.text),
    category: category(value.category),
    latitude: finiteNumber(value.latitude),
    longitude: finiteNumber(value.longitude),
    reportedAt: dateTime(value.reported_at),
    photoPath,
  }
}

function decodeCentroid(value: unknown): Readonly<{ latitude: number; longitude: number }> {
  if (!hasExactKeys(value, CENTROID_KEYS)) return invalidResponse()
  return { latitude: finiteNumber(value.latitude), longitude: finiteNumber(value.longitude) }
}

function decodeIncident(value: unknown): IncidentSummary {
  if (!hasExactKeys(value, INCIDENT_KEYS)) return invalidResponse()
  return {
    incidentId: uuid(value.incident_id),
    status: status(value.status),
    categories: isDenseArray(value.category_summary)
      ? value.category_summary.map(category)
      : invalidResponse(),
    priority: decodePriority(value.priority),
    confirmedReportCount: finiteNumber(value.confirmed_report_count),
    pendingCandidateCount: finiteNumber(value.pending_candidate_count),
    centroid: decodeCentroid(value.centroid),
    radiusMetres: finiteNumber(value.radius_metres),
    earliestReportedAt: dateTime(value.earliest_reported_at),
    latestReportedAt: dateTime(value.latest_reported_at),
    conflictReasons: strings(value.conflict_reasons),
  }
}

function matchState(value: unknown): IncidentRelationship["decision"] {
  switch (value) {
    case "auto_match":
    case "no_match":
    case "review_required":
      return value
    default:
      return invalidResponse()
  }
}

function decisionSource(value: unknown): IncidentRelationship["decisionSource"] {
  switch (value) {
    case "automated":
    case "officer_review":
      return value
    default:
      return invalidResponse()
  }
}

function decodeEdge(value: unknown): IncidentRelationship {
  if (!hasExactKeys(value, EDGE_KEYS)) return invalidResponse()
  return {
    leftId: uuid(value.left_id),
    rightId: uuid(value.right_id),
    decision: matchState(value.decision),
    reasons: strings(value.reasons),
    decisionSource: decisionSource(value.decision_source),
    matcherRecommendation: value.matcher_recommendation === null
      ? null
      : matchState(value.matcher_recommendation),
  }
}

function decodeTransition(value: unknown): IncidentTransition {
  if (!hasExactKeys(value, TRANSITION_KEYS)) return invalidResponse()
  return {
    previousIncidentSnapshotIds: value.previous_incident_snapshot_ids instanceof Array
      ? value.previous_incident_snapshot_ids.map(uuid)
      : invalidResponse(),
    currentIncidentSnapshotIds: value.current_incident_snapshot_ids instanceof Array
      ? value.current_incident_snapshot_ids.map(uuid)
      : invalidResponse(),
  }
}

export function decodeComplaintSubmission(value: unknown): ComplaintSubmission {
  if (!hasExactKeys(value, SUBMISSION_KEYS)) return invalidResponse()
  if (!isDenseArray(value.relationship_decisions) || !isDenseArray(value.incidents)
    || !isDenseArray(value.priorities)) return invalidResponse()
  return {
    complaint: decodeComplaint(value.complaint),
    created: value.created === true,
    replayed: value.replayed === true,
    relationshipDecisions: value.relationship_decisions.map(decodeEdge),
    incidentTransition: decodeTransition(value.incident_transition),
    incidents: value.incidents.map(decodeIncident),
    priorities: value.priorities.map(decodePriority),
  }
}
