import type { IncidentPage } from "../domain/incident"

export const validIncidentListTransportFixture = {
  items: [
    {
      incident_id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
      status: "confirmed",
      category_summary: ["street_light", "blocked_drain"],
      priority: {
        level: "high",
        reasons: ["Multiple confirmed reports"],
        policy_version: "priority-v1",
      },
      confirmed_report_count: 3,
      pending_candidate_count: 1,
      centroid: { latitude: 1.3521, longitude: 103.8198 },
      radius_metres: 125.5,
      earliest_reported_at: "2026-07-16T01:00:00+00:00",
      latest_reported_at: "2026-07-16T03:00:00Z",
      conflict_reasons: [],
    },
    {
      incident_id: "00000000-0000-4000-8000-000000000000",
      status: "conflict",
      category_summary: ["other", "flooding"],
      priority: null,
      confirmed_report_count: 2,
      pending_candidate_count: 0,
      centroid: { latitude: 1.3, longitude: 103.8 },
      radius_metres: 80,
      earliest_reported_at: "2026-07-15T23:30:00Z",
      latest_reported_at: "2026-07-16T02:30:00+00:00",
      conflict_reasons: ["category_conflict"],
    },
  ],
  limit: 100,
  offset: 0,
  total: 2,
} as const

export const reorderedIncidentListTransportFixture = {
  ...validIncidentListTransportFixture,
  items: [
    {
      ...validIncidentListTransportFixture.items[1],
      category_summary: ["flooding", "other"],
    },
    {
      ...validIncidentListTransportFixture.items[0],
      category_summary: ["blocked_drain", "street_light"],
    },
  ],
} as const

export const incidentPageFixture = {
  items: [
    {
      incidentId: "ffffffff-ffff-4fff-8fff-ffffffffffff",
      status: "confirmed",
      categories: ["street_light", "blocked_drain"],
      priority: {
        level: "high",
        reasons: ["Multiple confirmed reports"],
        policyVersion: "priority-v1",
      },
      confirmedReportCount: 3,
      pendingCandidateCount: 1,
      centroid: { latitude: 1.3521, longitude: 103.8198 },
      radiusMetres: 125.5,
      earliestReportedAt: "2026-07-16T01:00:00+00:00",
      latestReportedAt: "2026-07-16T03:00:00Z",
      conflictReasons: [],
    },
    {
      incidentId: "00000000-0000-4000-8000-000000000000",
      status: "conflict",
      categories: ["other", "flooding"],
      priority: null,
      confirmedReportCount: 2,
      pendingCandidateCount: 0,
      centroid: { latitude: 1.3, longitude: 103.8 },
      radiusMetres: 80,
      earliestReportedAt: "2026-07-15T23:30:00Z",
      latestReportedAt: "2026-07-16T02:30:00+00:00",
      conflictReasons: ["category_conflict"],
    },
  ],
  limit: 100,
  offset: 0,
  total: 2,
} as const satisfies IncidentPage

export const validIncidentDetailTransportFixture = {
  ...validIncidentListTransportFixture.items[0],
  complaint_ids: ["00000000-0000-4000-8000-000000000001"],
  review_candidate_ids: [],
  confirmed_edges: [],
  review_candidates: [],
  confirmed_reports: {
    items: [
      {
        complaint_id: "00000000-0000-4000-8000-000000000001",
        text: "Street light is out near the community hall",
        category: "street_light",
        latitude: 1.3522,
        longitude: 103.8199,
        reported_at: "2026-07-16T02:15:00Z",
        photo_available: true,
      },
    ],
    total: 4,
    has_more: true,
  },
} as const

export const incidentDetailFixture = {
  incidentId: validIncidentDetailTransportFixture.incident_id,
  status: validIncidentDetailTransportFixture.status,
  categories: validIncidentDetailTransportFixture.category_summary,
  priority: {
    level: "high",
    reasons: ["Multiple confirmed reports"],
    policyVersion: "priority-v1",
  },
  confirmedReportCount: validIncidentDetailTransportFixture.confirmed_report_count,
  pendingCandidateCount: validIncidentDetailTransportFixture.pending_candidate_count,
  centroid: validIncidentDetailTransportFixture.centroid,
  radiusMetres: validIncidentDetailTransportFixture.radius_metres,
  earliestReportedAt: validIncidentDetailTransportFixture.earliest_reported_at,
  latestReportedAt: validIncidentDetailTransportFixture.latest_reported_at,
  conflictReasons: validIncidentDetailTransportFixture.conflict_reasons,
  complaintIds: validIncidentDetailTransportFixture.complaint_ids,
  reviewCandidateIds: validIncidentDetailTransportFixture.review_candidate_ids,
  confirmedEdges: [],
  reviewCandidates: [],
  confirmedReports: {
    items: [
      {
        complaintId: "00000000-0000-4000-8000-000000000001",
        text: "Street light is out near the community hall",
        category: "street_light",
        latitude: 1.3522,
        longitude: 103.8199,
        reportedAt: "2026-07-16T02:15:00Z",
        photoAvailable: true,
      },
    ],
    total: 4,
    hasMore: true,
  },
} as const
