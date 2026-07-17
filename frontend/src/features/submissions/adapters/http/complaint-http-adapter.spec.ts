import { describe, expect, it } from "vitest"

import type { ComplaintSubmissionResult } from "../../application/complaint-port"
import { ComplaintHttpAdapter } from "./complaint-http-adapter"

const responseFixture = {
  complaint: {
    complaint_id: "00000000-0000-4000-8000-000000000001",
    text: "Blocked drain near the market",
    category: "blocked_drain",
    latitude: 3.07,
    longitude: 101.52,
    reported_at: "2026-07-17T00:00:00Z",
    photo_path: "field-photo.jpg",
  },
  created: true,
  replayed: false,
  relationship_decisions: [],
  incident_transition: {
    previous_incident_snapshot_ids: [],
    current_incident_snapshot_ids: [],
  },
  incidents: [],
  priorities: [],
} as const

describe("ComplaintHttpAdapter", () => {
  it("posts the frozen JSON contract with an idempotency key and preserves the photo reference", async () => {
    let capturedUrl = ""
    let capturedInit: RequestInit | undefined
    const adapter = new ComplaintHttpAdapter({
      baseUrl: "/api/v1",
      fetch: (input, init) => {
        if (typeof input === "string") capturedUrl = input
        else if (input instanceof URL) capturedUrl = input.href
        else capturedUrl = input.url
        capturedInit = init
        return Promise.resolve(new Response(JSON.stringify(responseFixture), { status: 201 }))
      },
    })

    const result: ComplaintSubmissionResult = await adapter.submit(
      {
        text: responseFixture.complaint.text,
        latitude: responseFixture.complaint.latitude,
        longitude: responseFixture.complaint.longitude,
        reportedAt: responseFixture.complaint.reported_at,
        category: responseFixture.complaint.category,
        photoId: "00000000-0000-4000-8000-000000000099",
      },
      "key-1",
      new AbortController().signal,
    )

    expect(capturedUrl).toBe("/api/v1/complaints")
    expect(capturedInit?.headers).toEqual({
      "Content-Type": "application/json",
      "Idempotency-Key": "key-1",
    })
    const body = capturedInit?.body
    expect(typeof body).toBe("string")
    if (typeof body === "string") {
      expect(JSON.parse(body)).toMatchObject({
        photo_id: "00000000-0000-4000-8000-000000000099",
      })
      expect(JSON.parse(body)).not.toHaveProperty("photo_path")
    }
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.submission.complaint.photoPath).toBe("field-photo.jpg")
  })

  it("keeps an idempotency conflict explicit", async () => {
    const adapter = new ComplaintHttpAdapter({
      baseUrl: "/api/v1",
      fetch: () => Promise.resolve(new Response("{}", { status: 409 })),
    })
    const result = await adapter.submit(
      {
        text: "A report",
        latitude: 3,
        longitude: 101,
        reportedAt: "2026-07-17T00:00:00Z",
        category: null,
        photoId: null,
      },
      "key-1",
      new AbortController().signal,
    )

    expect(result).toEqual({ ok: false, error: { kind: "conflict", status: 409 } })
  })
})