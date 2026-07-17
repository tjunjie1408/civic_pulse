import { describe, expect, it } from "vitest"

import { extractPhotoGps, MAX_PHOTO_BYTES, validatePhoto } from "./photo"

function fakeFile(type: string, size: number): File {
  const file = new File(["photo"], "evidence.jpg", { type })
  Object.defineProperty(file, "size", { value: size })
  return file
}

describe("photo evidence helpers", () => {
  it("accepts JPEG and PNG files up to the configured limit", () => {
    expect(validatePhoto(fakeFile("image/jpeg", MAX_PHOTO_BYTES))).toEqual({ ok: true })
    expect(validatePhoto(fakeFile("image/png", MAX_PHOTO_BYTES))).toEqual({ ok: true })
  })

  it("rejects unsupported formats and oversized files", () => {
    expect(validatePhoto(fakeFile("image/gif", 10))).toEqual({
      ok: false,
      error: "Use a JPEG or PNG photo.",
    })
    expect(validatePhoto(fakeFile("image/jpeg", MAX_PHOTO_BYTES + 1))).toEqual({
      ok: false,
      error: "Keep the photo under 8 MB.",
    })
  })

  it("returns finite EXIF GPS coordinates and treats unavailable metadata as normal", async () => {
    const file = fakeFile("image/jpeg", 10)

    await expect(extractPhotoGps(file, () => Promise.resolve({ latitude: 3.07, longitude: 101.52 }))).resolves.toEqual({
      latitude: 3.07,
      longitude: 101.52,
    })
    await expect(extractPhotoGps(file, () => Promise.resolve({ latitude: Number.NaN, longitude: 101.52 }))).resolves.toBeNull()
    await expect(extractPhotoGps(file, () => Promise.reject(new Error("no exif")))).resolves.toBeNull()
  })
})
