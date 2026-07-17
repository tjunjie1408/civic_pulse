import type { components } from "../../../incidents/adapters/http/generated/openapi"
import type {
  PhotoUploadPort,
  PhotoUploadResult,
} from "../../application/photo-upload-port"

interface PhotoHttpAdapterDependencies {
  readonly baseUrl: string
  readonly fetch: typeof globalThis.fetch
}

type PhotoUploadResponse = components["schemas"]["PhotoUploadResponse"]

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function isAbortError(error: unknown): boolean {
  return typeof error === "object" && error !== null && "name" in error && error.name === "AbortError"
}

function decodePhotoId(value: unknown): PhotoUploadResponse["photo_id"] {
  if (typeof value !== "object" || value === null || !("photo_id" in value)) {
    throw new TypeError("Invalid photo-upload response")
  }
  const photoId = value.photo_id
  if (typeof photoId !== "string" || !UUID_PATTERN.test(photoId)) {
    throw new TypeError("Invalid photo-upload response")
  }
  return photoId
}

export class PhotoHttpAdapter implements PhotoUploadPort {
  constructor(private readonly dependencies: PhotoHttpAdapterDependencies) {}

  async upload(file: File, signal: AbortSignal): Promise<PhotoUploadResult> {
    const body = new FormData()
    body.append("file", file, file.name)
    let response: Response
    try {
      response = await this.dependencies.fetch(`${this.dependencies.baseUrl}/photos`, {
        method: "POST",
        body,
        signal,
      })
    } catch (error: unknown) {
      return { ok: false, error: { kind: isAbortError(error) ? "aborted" : "network" } }
    }
    if (response.status === 415) {
      return { ok: false, error: { kind: "unsupported", status: response.status } }
    }
    if (response.status === 413) {
      return { ok: false, error: { kind: "too_large", status: response.status } }
    }
    if (!response.ok) return { ok: false, error: { kind: "service", status: response.status } }
    try {
      return { ok: true, photoId: decodePhotoId(await response.json()) }
    } catch (error: unknown) {
      return { ok: false, error: { kind: isAbortError(error) ? "aborted" : "contract" } }
    }
  }
}
