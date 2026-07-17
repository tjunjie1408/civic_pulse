import type { PhotoUploadPort, PhotoUploadResult } from "./photo-upload-port"

export class UploadPhoto {
  constructor(private readonly port: PhotoUploadPort) {}

  execute(file: File, signal: AbortSignal): Promise<PhotoUploadResult> {
    return this.port.upload(file, signal)
  }
}
