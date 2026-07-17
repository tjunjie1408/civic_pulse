import { describe, expect, it } from "vitest"

import type { ComplaintSubmission, ComplaintSubmissionRequest } from "../domain/complaint"
import type { ComplaintPort } from "./complaint-port"

describe("ComplaintPort", () => {
  it("describes the JSON complaint request without binary upload semantics", () => {
    const request: ComplaintSubmissionRequest = {
      text: "Blocked drain near the market",
      latitude: 3.07,
      longitude: 101.52,
      reportedAt: "2026-07-17T00:00:00Z",
      category: "blocked_drain",
      photoPath: "field-photo.jpg",
    }

    const submission: ComplaintSubmission = {
      complaint: {
        complaintId: "00000000-0000-4000-8000-000000000001",
        ...request,
      },
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
        void idempotencyKey
        void signal
        return Promise.resolve({
          ok: true as const,
          submission: { ...submission, complaint: { ...submission.complaint, ...candidate } },
        })
      },
    }

    expect(port).toBeDefined()
    expect(request.photoPath).toBe("field-photo.jpg")
  })
})
