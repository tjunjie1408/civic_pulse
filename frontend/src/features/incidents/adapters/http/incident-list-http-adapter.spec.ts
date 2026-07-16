import { describe, expect, it, vi } from "vitest"

import {
  incidentPageFixture,
  validIncidentListTransportFixture,
} from "../../testing/incident-fixtures"
import { IncidentListHttpAdapter } from "./incident-list-http-adapter"

const initialQuery = { limit: 100, offset: 0 } as const

function responseWithJson(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  })
}

describe("IncidentListHttpAdapter", () => {
  it("gets the requested page with the caller's identical signal and preserves API order", async () => {
    const fetchStub = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(responseWithJson(validIncidentListTransportFixture))
    const adapter = new IncidentListHttpAdapter({
      baseUrl: "/api/v1",
      fetch: fetchStub,
    })
    const signal = new AbortController().signal

    const result = await adapter.list(initialQuery, signal)

    expect(fetchStub).toHaveBeenCalledOnce()
    expect(fetchStub).toHaveBeenCalledWith("/api/v1/incidents?limit=100&offset=0", {
      method: "GET",
      signal,
    })
    expect(fetchStub.mock.calls[0]?.[1]?.signal).toBe(signal)
    expect(result).toEqual({ ok: true, page: incidentPageFixture })
    expect(result.ok && result.page.items.map(({ incidentId }) => incidentId)).toEqual([
      "ffffffff-ffff-4fff-8fff-ffffffffffff",
      "00000000-0000-4000-8000-000000000000",
    ])
  })

  it("classifies a fetch rejection as a network failure", async () => {
    const fetchStub = vi.fn<typeof globalThis.fetch>().mockRejectedValue(new Error("offline"))
    const adapter = new IncidentListHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    await expect(adapter.list(initialQuery, new AbortController().signal)).resolves.toEqual({
      ok: false,
      error: { kind: "network" },
    })
  })

  it("classifies an AbortError as an aborted request", async () => {
    const fetchStub = vi
      .fn<typeof globalThis.fetch>()
      .mockRejectedValue(new DOMException("request aborted", "AbortError"))
    const adapter = new IncidentListHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    await expect(adapter.list(initialQuery, new AbortController().signal)).resolves.toEqual({
      ok: false,
      error: { kind: "aborted" },
    })
  })

  it.each([422, 500, 503])(
    "classifies HTTP %i by status without reading or exposing its response body",
    async (status) => {
      const response = responseWithJson(
        { detail: "internal server detail that must remain private" },
        status,
      )
      const fetchStub = vi.fn<typeof globalThis.fetch>().mockResolvedValue(response)
      const adapter = new IncidentListHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

      const result = await adapter.list(initialQuery, new AbortController().signal)

      expect(result).toEqual({ ok: false, error: { kind: "service", status } })
      expect(response.bodyUsed).toBe(false)
    },
  )

  it.each([
    ["invalid JSON", new Response("not-json", { status: 200 })],
    ["an invalid 200 shape", responseWithJson({ items: [] })],
  ])("classifies %s as a contract failure", async (_description, response) => {
    const fetchStub = vi.fn<typeof globalThis.fetch>().mockResolvedValue(response)
    const adapter = new IncidentListHttpAdapter({ baseUrl: "/api/v1", fetch: fetchStub })

    await expect(adapter.list(initialQuery, new AbortController().signal)).resolves.toEqual({
      ok: false,
      error: { kind: "contract" },
    })
  })
})
