import type {
  IncidentCategory,
  IncidentPage,
  IncidentStatus,
  IncidentSummary,
  OperationalPriority,
  OperationalPriorityLevel,
} from "../../domain/incident"
import type { components } from "./generated/openapi"

type IncidentListTransport = components["schemas"]["IncidentListResponse"]
type IncidentTransport = IncidentListTransport["items"][number]
type CentroidTransport = IncidentTransport["centroid"]
type PriorityTransport = NonNullable<IncidentTransport["priority"]>

const PAGE_KEYS = ["items", "limit", "offset", "total"] as const satisfies readonly (
  keyof IncidentListTransport
)[]
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
const CENTROID_KEYS = ["latitude", "longitude"] as const satisfies readonly (
  keyof CentroidTransport
)[]
const PRIORITY_KEYS = ["level", "reasons", "policy_version"] as const satisfies readonly (
  keyof PriorityTransport
)[]

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ISO_DATE_TIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})[Tt](?:[01]\d|2[0-3]):[0-5]\d:(?:[0-5]\d|60)(?:\.\d+)?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/

function invalidResponse(): never {
  throw new TypeError("Invalid incident-list response")
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
  if (!Array.isArray(value)) {
    return false
  }
  for (let index = 0; index < value.length; index += 1) {
    if (!Object.hasOwn(value, index)) {
      return false
    }
  }
  return true
}

function requireFiniteNumber(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return invalidResponse()
  }
  return value
}

function requireString(value: unknown): string {
  if (typeof value !== "string") {
    return invalidResponse()
  }
  return value
}

function requireUuid(value: unknown): string {
  const uuid = requireString(value)
  if (!UUID_PATTERN.test(uuid)) {
    return invalidResponse()
  }
  return uuid
}

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
}

function requireIsoDateTime(value: unknown): string {
  const dateTime = requireString(value)
  const match = ISO_DATE_TIME_PATTERN.exec(dateTime)
  if (match === null) {
    return invalidResponse()
  }

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const daysInMonth = [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  const maximumDay = daysInMonth[month - 1]
  if (maximumDay === undefined || day < 1 || day > maximumDay) {
    return invalidResponse()
  }
  return dateTime
}

function decodeStringArray(value: unknown): readonly string[] {
  if (!isDenseArray(value)) {
    return invalidResponse()
  }
  return value.map(requireString)
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
  if (!isDenseArray(value)) {
    return invalidResponse()
  }
  return value.map(decodeCategory)
}

function decodeStatus(value: unknown): IncidentStatus {
  switch (value) {
    case "confirmed":
    case "isolated":
    case "conflict":
      return value
    default:
      return invalidResponse()
  }
}

function decodePriorityLevel(value: unknown): OperationalPriorityLevel {
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
  if (value === null) {
    return null
  }
  if (!hasExactKeys(value, PRIORITY_KEYS)) {
    return invalidResponse()
  }
  return {
    level: decodePriorityLevel(value.level),
    reasons: decodeStringArray(value.reasons),
    policyVersion: requireString(value.policy_version),
  }
}

function decodeCentroid(value: unknown): Readonly<{ latitude: number; longitude: number }> {
  if (!hasExactKeys(value, CENTROID_KEYS)) {
    return invalidResponse()
  }
  return {
    latitude: requireFiniteNumber(value.latitude),
    longitude: requireFiniteNumber(value.longitude),
  }
}

function decodeIncident(value: unknown): IncidentSummary {
  if (!hasExactKeys(value, INCIDENT_KEYS)) {
    return invalidResponse()
  }
  return {
    incidentId: requireUuid(value.incident_id),
    status: decodeStatus(value.status),
    categories: decodeCategories(value.category_summary),
    priority: decodePriority(value.priority),
    confirmedReportCount: requireFiniteNumber(value.confirmed_report_count),
    pendingCandidateCount: requireFiniteNumber(value.pending_candidate_count),
    centroid: decodeCentroid(value.centroid),
    radiusMetres: requireFiniteNumber(value.radius_metres),
    earliestReportedAt: requireIsoDateTime(value.earliest_reported_at),
    latestReportedAt: requireIsoDateTime(value.latest_reported_at),
    conflictReasons: decodeStringArray(value.conflict_reasons),
  }
}

export function decodeIncidentList(value: unknown): IncidentPage {
  if (!hasExactKeys(value, PAGE_KEYS) || !isDenseArray(value.items)) {
    return invalidResponse()
  }
  return {
    items: value.items.map(decodeIncident),
    limit: requireFiniteNumber(value.limit),
    offset: requireFiniteNumber(value.offset),
    total: requireFiniteNumber(value.total),
  }
}
