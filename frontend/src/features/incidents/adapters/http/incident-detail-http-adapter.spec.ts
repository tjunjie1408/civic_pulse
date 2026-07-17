import { describe, expect, it, vi } from "vitest"

import { IncidentDetailHttpAdapter } from "./incident-detail-http-adapter"

const detailTransport = {
  incident_id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
  status: "confirmed",
  category_summary: ["flooding"],
  priority: null,
  confirmed_report_count: 2,
  pending_candidate_count: 0,
  centroid: { latitude: 3.08, longitude: 101.52 },
  radius_metres: 100,
  earliest_reported_at: "2026-07-16T01:00:00Z",
  latest_reported_at: "2026-07-16T02:00:00Z",
  conflict_reasons: [],
  complaint_ids: [],
  review_candidate_ids: [],
  confirmed_edges: [],
  review_candidates: [],
  confirmed_reports: { items: [], total: 0, has_more: false },
} as const

function responseWithJson(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  })
}

describe("IncidentDetailHttpAdapter", () => {
  it("gets one snapshot with the caller's ID and identical abort signal", async () => {
    const fetchStub = vi.fn<typeof globalThis.fetch>().mockResolvedValue(responseWithJson(detailTransport))
    const adapter = new IncidentDetailHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })
    const signal = new AbortController().signal

    const result = await adapter.get(detailTransport.incident_id, signal)

    expect(fetchStub).toHaveBeenCalledWith(
      `/api/v1/incidents/${detailTransport.incident_id}`,
      { method: "GET", signal },
    )
    expect(result.ok && result.detail.incidentId).toBe(detailTransport.incident_id)
    expect(result.ok && result.detail.priority).toBeNull()
  })

  it("classifies 404 as a missing detail without reading its body", async () => {
    const response = responseWithJson({ detail: "private" }, 404)
    const fetchStub = vi.fn<typeof globalThis.fetch>().mockResolvedValue(response)
    const adapter = new IncidentDetailHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    await expect(adapter.get(detailTransport.incident_id, new AbortController().signal)).resolves.toEqual({
      ok: false,
      error: { kind: "missing" },
    })
    expect(response.bodyUsed).toBe(false)
  })

  it.each([422, 500, 503])("classifies HTTP %i as a service failure", async (status) => {
    const fetchStub = vi.fn<typeof globalThis.fetch>().mockResolvedValue(responseWithJson({}, status))
    const adapter = new IncidentDetailHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    await expect(adapter.get(detailTransport.incident_id, new AbortController().signal)).resolves.toEqual({
      ok: false,
      error: { kind: "service", status },
    })
  })

  it("classifies malformed JSON and payloads as contract failures", async () => {
    const fetchStub = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(new Response("not-json", { status: 200 }))
      .mockResolvedValueOnce(responseWithJson({ status: "confirmed" }))
    const adapter = new IncidentDetailHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })
    const signal = new AbortController().signal

    await expect(adapter.get(detailTransport.incident_id, signal)).resolves.toEqual({
      ok: false,
      error: { kind: "contract" },
    })
    await expect(adapter.get(detailTransport.incident_id, signal)).resolves.toEqual({
      ok: false,
      error: { kind: "contract" },
    })
  })

  it.each([
    ["network", new Error("offline")],
    ["aborted", new DOMException("request aborted", "AbortError")],
  ] as const)("classifies a %s fetch rejection", async (kind, error) => {
    const fetchStub = vi.fn<typeof globalThis.fetch>().mockRejectedValue(error)
    const adapter = new IncidentDetailHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    await expect(adapter.get(detailTransport.incident_id, new AbortController().signal)).resolves.toEqual({
      ok: false,
      error: { kind },
    })
  })
})
