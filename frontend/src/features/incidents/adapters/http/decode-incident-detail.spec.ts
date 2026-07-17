import { describe, expect, it } from "vitest"

import { decodeIncidentDetail } from "./decode-incident-detail"

const validTransport = {
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
  complaint_ids: ["00000000-0000-4000-8000-000000000000"],
  review_candidate_ids: ["11111111-1111-4111-8111-111111111111"],
  confirmed_edges: [
    {
      left_id: "00000000-0000-4000-8000-000000000000",
      right_id: "22222222-2222-4222-8222-222222222222",
      decision: "auto_match",
      reasons: ["same location"],
      decision_source: "automated",
      matcher_recommendation: "auto_match",
    },
  ],
  review_candidates: [
    {
      left_id: "00000000-0000-4000-8000-000000000000",
      right_id: "11111111-1111-4111-8111-111111111111",
      decision: "review_required",
      reasons: ["conflicting category"],
      decision_source: "officer_review",
      matcher_recommendation: null,
    },
  ],
} as const

describe("decodeIncidentDetail", () => {
  it("maps the snapshot detail without changing evidence order or field semantics", () => {
    const detail = decodeIncidentDetail(validTransport)

    expect(detail).toEqual({
      incidentId: validTransport.incident_id,
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
      earliestReportedAt: validTransport.earliest_reported_at,
      latestReportedAt: validTransport.latest_reported_at,
      conflictReasons: [],
      complaintIds: ["00000000-0000-4000-8000-000000000000"],
      reviewCandidateIds: ["11111111-1111-4111-8111-111111111111"],
      confirmedEdges: [
        {
          leftId: "00000000-0000-4000-8000-000000000000",
          rightId: "22222222-2222-4222-8222-222222222222",
          decision: "auto_match",
          reasons: ["same location"],
          decisionSource: "automated",
          matcherRecommendation: "auto_match",
        },
      ],
      reviewCandidates: [
        {
          leftId: "00000000-0000-4000-8000-000000000000",
          rightId: "11111111-1111-4111-8111-111111111111",
          decision: "review_required",
          reasons: ["conflicting category"],
          decisionSource: "officer_review",
          matcherRecommendation: null,
        },
      ],
    })
  })

  it("preserves a null operational priority", () => {
    expect(decodeIncidentDetail({ ...validTransport, priority: null }).priority).toBeNull()
  })

  it("rejects missing, extra, malformed, or sparse nested fields", () => {
    const missing = { ...validTransport } as Record<string, unknown>
    delete missing.complaint_ids

    expect(() => decodeIncidentDetail(missing)).toThrow(TypeError)
    expect(() => decodeIncidentDetail({ ...validTransport, unexpected: true })).toThrow(TypeError)
    expect(() =>
      decodeIncidentDetail({
        ...validTransport,
        confirmed_edges: [{ ...validTransport.confirmed_edges[0], left_id: "invalid" }],
      }),
    ).toThrow(TypeError)
    expect(() =>
      decodeIncidentDetail({ ...validTransport, review_candidate_ids: new Array<unknown>(1) }),
    ).toThrow(TypeError)
  })

  it("rejects an invalid priority level instead of inventing an operational mapping", () => {
    expect(() =>
      decodeIncidentDetail({
        ...validTransport,
        priority: { ...validTransport.priority, level: "review_required" },
      }),
    ).toThrow(TypeError)
  })
})
