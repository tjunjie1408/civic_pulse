import type {
  IncidentCategory,
  IncidentRelationship,
  IncidentSummary,
  OperationalPriority,
} from "../../incidents/domain/incident"

export interface ComplaintSubmissionRequest {
  readonly text: string
  readonly latitude: number
  readonly longitude: number
  readonly reportedAt: string
  readonly category: IncidentCategory | null
  readonly photoId: string | null
}

export interface SubmittedComplaint {
  readonly complaintId: string
  readonly text: string
  readonly latitude: number
  readonly longitude: number
  readonly reportedAt: string
  readonly category: IncidentCategory | null
  readonly photoPath: string | null
}

export interface IncidentTransition {
  readonly previousIncidentSnapshotIds: readonly string[]
  readonly currentIncidentSnapshotIds: readonly string[]
}

export interface ComplaintSubmission {
  readonly complaint: SubmittedComplaint
  readonly created: boolean
  readonly replayed: boolean
  readonly relationshipDecisions: readonly IncidentRelationship[]
  readonly incidentTransition: IncidentTransition
  readonly incidents: readonly IncidentSummary[]
  readonly priorities: readonly (OperationalPriority | null)[]
}