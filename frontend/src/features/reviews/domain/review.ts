import type {
  IncidentCategory,
  IncidentStatus,
} from "../../incidents/domain/incident"

export type ReviewStatus = "pending" | "approved" | "rejected"
export type ReviewMatchState = "auto_match" | "no_match" | "review_required"
export type ReviewDecisionSource = "automated" | "officer_review"
export type ReviewLocationCompatibility = "compatible" | "conflicting" | "unknown"
export type ReviewLocationEntityKind = "block" | "unit" | "street" | "landmark"
export type ReviewPriorityLevel = "critical" | "high" | "medium" | "low" | "review_required"

export interface ReviewPriority {
  readonly level: ReviewPriorityLevel
  readonly reasons: readonly string[]
  readonly policyVersion: string
}

export interface ReviewSummary {
  readonly reviewId: string
  readonly leftComplaintId: string
  readonly rightComplaintId: string
  readonly originalMatcherRecommendation: ReviewMatchState
  readonly matcherReasons: readonly string[]
  readonly status: ReviewStatus
  readonly createdAt: string
  readonly resolvedAt: string | null
  readonly reviewerId: string | null
  readonly reviewNote: string | null
  readonly finalRelationshipState: ReviewMatchState | null
  readonly decisionSource: ReviewDecisionSource | null
  readonly graphVersion: string
}

export interface ReviewComplaint {
  readonly complaintId: string
  readonly text: string
  readonly category: IncidentCategory
  readonly latitude: number
  readonly longitude: number
  readonly reportedAt: string
  readonly photoAvailable: boolean
}

export interface ReviewLocationEntity {
  readonly kind: ReviewLocationEntityKind
  readonly value: string
  readonly raw: string
}

export interface ReviewMatcherEvidence {
  readonly semanticSimilarity: number
  readonly geoDistanceMetres: number
  readonly timeDifferenceSeconds: number
  readonly categoryCompatibility: boolean
  readonly locationCompatibility: ReviewLocationCompatibility
  readonly firstLocationEntities: readonly ReviewLocationEntity[]
  readonly secondLocationEntities: readonly ReviewLocationEntity[]
}

export interface ReviewDetail {
  readonly reviewId: string
  readonly status: ReviewStatus
  readonly complaintA: ReviewComplaint
  readonly complaintB: ReviewComplaint
  readonly originalMatcherRecommendation: ReviewMatchState
  readonly matcherReasons: readonly string[]
  readonly matcherEvidence: ReviewMatcherEvidence | null
  readonly createdAt: string
  readonly resolvedAt: string | null
  readonly reviewerId: string | null
  readonly reviewNote: string | null
  readonly finalRelationshipState: ReviewMatchState | null
  readonly decisionSource: ReviewDecisionSource | null
  readonly graphVersion: string
  readonly previousIncidentSnapshotIds: readonly string[]
  readonly newIncidentSnapshotIds: readonly string[]
}

export interface ReviewPage {
  readonly items: readonly ReviewSummary[]
  readonly limit: number
  readonly offset: number
  readonly total: number
}

export interface ReviewAffectedIncident {
  readonly incidentId: string
  readonly status: IncidentStatus
  readonly categories: readonly IncidentCategory[]
  readonly priority: ReviewPriority | null
  readonly confirmedReportCount: number
  readonly pendingCandidateCount: number
  readonly centroid: Readonly<{ latitude: number; longitude: number }>
  readonly radiusMetres: number
  readonly earliestReportedAt: string
  readonly latestReportedAt: string
  readonly conflictReasons: readonly string[]
}

export interface ReviewMutation {
  readonly review: ReviewDetail
  readonly finalRelationshipState: ReviewMatchState
  readonly affectedComplaintIds: readonly string[]
  readonly previousIncidentSnapshotIds: readonly string[]
  readonly newIncidentSnapshotIds: readonly string[]
  readonly affectedIncidents: readonly ReviewAffectedIncident[]
  readonly resultingPriorities: readonly (ReviewPriority | null)[]
  readonly conflictStatus: IncidentStatus | null
}

export type ReviewResolutionRequest = Readonly<{
  reviewerId: string
  note: string | null
}>
