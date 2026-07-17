import type { ReviewDetail } from "./review"

export interface NeutralEvidencePoint {
  readonly key: "a" | "b"
  readonly label: "Complaint A" | "Complaint B"
  readonly latitude: number
  readonly longitude: number
  readonly x: number
  readonly y: number
}

export interface NeutralEvidenceProjection {
  readonly points: readonly [NeutralEvidencePoint, NeutralEvidencePoint]
}

export function projectNeutralEvidencePoints(detail: ReviewDetail): NeutralEvidenceProjection {
  const complaints = [detail.complaintA, detail.complaintB] as const
  const latitudes = complaints.map((complaint) => complaint.latitude)
  const longitudes = complaints.map((complaint) => complaint.longitude)
  const minLatitude = Math.min(...latitudes)
  const maxLatitude = Math.max(...latitudes)
  const minLongitude = Math.min(...longitudes)
  const maxLongitude = Math.max(...longitudes)
  const latitudeRange = maxLatitude - minLatitude
  const longitudeRange = maxLongitude - minLongitude
  const sameLocation = latitudeRange === 0 && longitudeRange === 0

  const project = (latitude: number, longitude: number, index: 0 | 1): NeutralEvidencePoint => ({
    key: index === 0 ? "a" : "b",
    label: index === 0 ? "Complaint A" : "Complaint B",
    latitude,
    longitude,
    x: sameLocation
      ? index === 0 ? 28 : 72
      : 18 + ((longitude - minLongitude) / (longitudeRange || 1)) * 64,
    y: sameLocation
      ? 50
      : 82 - ((latitude - minLatitude) / (latitudeRange || 1)) * 64,
  })

  return {
    points: [
      project(complaints[0].latitude, complaints[0].longitude, 0),
      project(complaints[1].latitude, complaints[1].longitude, 1),
    ],
  }
}
