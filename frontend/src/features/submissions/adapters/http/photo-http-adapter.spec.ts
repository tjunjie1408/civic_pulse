import { describe, expect, it, vi } from "vitest"

import { PhotoHttpAdapter } from "./photo-http-adapter"

const PHOTO_ID = "30000000-0000-0000-0000-000000000001"

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function jpegFile(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], "evidence.jpg", {
    type: "image/jpeg",
  })
}

describe("PhotoHttpAdapter", () => {
  it("posts multipart form data and returns the photo id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ photo_id: PHOTO_ID, media_type: "image/jpeg", byte_size: 4 }, 201),
    )
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result).toEqual({ ok: true, photoId: PHOTO_ID })
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/v1/photos")
    expect(init.method).toBe("POST")
    expect(init.body).toBeInstanceOf(FormData)
    const sent = (init.body as FormData).get("file")
    expect(sent).toBeInstanceOf(File)
  })

  it.each([
    [415, "unsupported"],
    [413, "too_large"],
    [500, "service"],
  ])("maps HTTP %d to the %s error kind", async (status, kind) => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ error: { code: "x", message: "x", details: {}, request_id: "r" } }, status),
    )
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error.kind).toBe(kind)
  })

  it("maps thrown fetch failures to network errors", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"))
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result).toEqual({ ok: false, error: { kind: "network" } })
  })

  it("maps aborted fetches to aborted errors", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError"))
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result).toEqual({ ok: false, error: { kind: "aborted" } })
  })

  it("rejects malformed success payloads as contract errors", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ photo_id: "not-a-uuid" }, 201))
    const adapter = new PhotoHttpAdapter({ baseUrl: "/api/v1", fetch: fetchMock })
    const result = await adapter.upload(jpegFile(), new AbortController().signal)
    expect(result).toEqual({ ok: false, error: { kind: "contract" } })
  })
})
