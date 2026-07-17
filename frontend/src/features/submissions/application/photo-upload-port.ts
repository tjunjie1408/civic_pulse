export type PhotoUploadError =
  | { readonly kind: "network" }
  | { readonly kind: "aborted" }
  | { readonly kind: "unsupported"; readonly status: number }
  | { readonly kind: "too_large"; readonly status: number }
  | { readonly kind: "service"; readonly status: number }
  | { readonly kind: "contract" }

export type PhotoUploadResult =
  | { readonly ok: true; readonly photoId: string }
  | { readonly ok: false; readonly error: PhotoUploadError }

export interface PhotoUploadPort {
  upload(file: File, signal: AbortSignal): Promise<PhotoUploadResult>
}
