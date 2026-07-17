import { describe, expect, it } from "vitest"

import type { ComplaintSubmission, ComplaintSubmissionRequest, SubmittedComplaint } from "../domain/complaint"
import type { ComplaintPort } from "./complaint-port"

describe("ComplaintPort", () => {
  it("describes the JSON complaint request without binary upload semantics", () => {
    const request: ComplaintSubmissionRequest = {
      text: "Blocked drain near the market",
      latitude: 3.07,
      longitude: 101.52,
      reportedAt: "2026-07-17T00:00:00Z",
      category: "blocked_drain",
      photoId: "00000000-0000-4000-8000-000000000099",
    }

    const complaint: SubmittedComplaint = {
      complaintId: "00000000-0000-4000-8000-000000000001",
      text: request.text,
      latitude: request.latitude,
      longitude: request.longitude,
      reportedAt: request.reportedAt,
      category: request.category,
      photoPath: "uploads/00000000-0000-4000-8000-000000000099.jpg",
    }

    const submission: ComplaintSubmission = {
      complaint,
      created: true,
      replayed: false,
      relationshipDecisions: [],
      incidentTransition: {
        previousIncidentSnapshotIds: [],
        currentIncidentSnapshotIds: [],
      },
      incidents: [],
      priorities: [],
    }
    const port: ComplaintPort = {
      submit: (candidate, idempotencyKey, signal) => {
        void candidate
        void idempotencyKey
        void signal
        return Promise.resolve({
          ok: true as const,
          submission: { ...submission, complaint: { ...complaint } },
        })
      },
    }

    expect(port).toBeDefined()
    expect(request.photoId).toBe("00000000-0000-4000-8000-000000000099")
    expect(submission.complaint.photoPath).toBe("uploads/00000000-0000-4000-8000-000000000099.jpg")
  })
})