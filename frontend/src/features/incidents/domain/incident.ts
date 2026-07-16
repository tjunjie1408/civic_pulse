export type IncidentStatus = "confirmed" | "isolated" | "conflict"

export type IncidentCategory =
  | "pothole"
  | "blocked_drain"
  | "flooding"
  | "rubbish"
  | "street_light"
  | "other"

export type OperationalPriorityLevel = "critical" | "high" | "medium" | "low"

export interface OperationalPriority {
  readonly level: OperationalPriorityLevel
  readonly reasons: readonly string[]
  readonly policyVersion: string
}

export interface IncidentSummary {
  readonly incidentId: string
  readonly status: IncidentStatus
  readonly categories: readonly IncidentCategory[]
  readonly priority: OperationalPriority | null
  readonly confirmedReportCount: number
  readonly pendingCandidateCount: number
  readonly centroid: Readonly<{ latitude: number; longitude: number }>
  readonly radiusMetres: number
  readonly earliestReportedAt: string
  readonly latestReportedAt: string
  readonly conflictReasons: readonly string[]
}

export interface IncidentPage {
  readonly items: readonly IncidentSummary[]
  readonly limit: number
  readonly offset: number
  readonly total: number
}
