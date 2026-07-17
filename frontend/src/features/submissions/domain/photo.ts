import exifr from "exifr"

export const MAX_PHOTO_BYTES = 8 * 1024 * 1024

export interface PhotoValidation {
  readonly ok: boolean
  readonly error?: string
}

export interface PhotoGps {
  readonly latitude: number
  readonly longitude: number
}

export type PhotoGpsReader = (file: File) => Promise<unknown>

export function validatePhoto(file: File): PhotoValidation {
  if (file.type !== "image/jpeg" && file.type !== "image/png") {
    return { ok: false, error: "Use a JPEG or PNG photo." }
  }
  if (file.size > MAX_PHOTO_BYTES) {
    return { ok: false, error: "Keep the photo under 8 MB." }
  }
  return { ok: true }
}

function isPhotoGps(value: unknown): value is PhotoGps {
  if (typeof value !== "object" || value === null) return false
  if (!("latitude" in value) || !("longitude" in value)) return false
  const candidate = value as { latitude?: unknown; longitude?: unknown }
  return typeof candidate.latitude === "number" && Number.isFinite(candidate.latitude)
    && typeof candidate.longitude === "number" && Number.isFinite(candidate.longitude)
    && candidate.latitude >= -90 && candidate.latitude <= 90
    && candidate.longitude >= -180 && candidate.longitude <= 180
}

export async function extractPhotoGps(
  file: File,
  readGps: PhotoGpsReader = (candidate) => exifr.gps(candidate),
): Promise<PhotoGps | null> {
  try {
    const value = await readGps(file)
    return isPhotoGps(value) ? value : null
  } catch {
    return null
  }
}
