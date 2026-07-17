import type { IncidentSummary } from "./incident"

const EARTH_RADIUS_METRES = 6_371_008.8
const CIRCLE_SEGMENTS = 64

type Coordinate = readonly [longitude: number, latitude: number]

interface RadiusPointGeometry {
  readonly type: "Point"
  readonly coordinates: Coordinate
}

interface RadiusPolygonGeometry {
  readonly type: "Polygon"
  readonly coordinates: readonly [readonly Coordinate[]]
}

export type RadiusGeometry = RadiusPointGeometry | RadiusPolygonGeometry

export interface RadiusFeature {
  readonly type: "Feature"
  readonly properties: Readonly<{
    incidentId: string
    radiusMetres: number
  }>
  readonly geometry: RadiusGeometry
}

export interface RadiusFeatureCollection {
  readonly type: "FeatureCollection"
  readonly features: readonly RadiusFeature[]
}

type RadiusIncident = Pick<IncidentSummary, "incidentId" | "centroid" | "radiusMetres">

function degreesToRadians(value: number): number {
  return (value * Math.PI) / 180
}

function radiansToDegrees(value: number): number {
  return (value * 180) / Math.PI
}

function destinationPoint(
  longitude: number,
  latitude: number,
  bearingRadians: number,
  distanceMetres: number,
): Coordinate {
  const angularDistance = distanceMetres / EARTH_RADIUS_METRES
  const latitudeRadians = degreesToRadians(latitude)
  const longitudeRadians = degreesToRadians(longitude)
  const destinationLatitude = Math.asin(
    Math.sin(latitudeRadians) * Math.cos(angularDistance) +
      Math.cos(latitudeRadians) * Math.sin(angularDistance) * Math.cos(bearingRadians),
  )
  const destinationLongitude =
    longitudeRadians +
    Math.atan2(
      Math.sin(bearingRadians) * Math.sin(angularDistance) * Math.cos(latitudeRadians),
      Math.cos(angularDistance) - Math.sin(latitudeRadians) * Math.sin(destinationLatitude),
    )

  return [
    radiansToDegrees(destinationLongitude),
    radiansToDegrees(destinationLatitude),
  ]
}

function radiusFeature(incident: RadiusIncident): RadiusFeature | null {
  const { latitude, longitude } = incident.centroid
  const radius = incident.radiusMetres
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    !Number.isFinite(radius) ||
    radius < 0
  ) {
    return null
  }

  if (radius === 0) {
    return {
      type: "Feature",
      properties: { incidentId: incident.incidentId, radiusMetres: radius },
      geometry: { type: "Point", coordinates: [longitude, latitude] },
    }
  }

  const ring = Array.from({ length: CIRCLE_SEGMENTS + 1 }, (_, index) =>
    destinationPoint(
      longitude,
      latitude,
      (index / CIRCLE_SEGMENTS) * Math.PI * 2,
      radius,
    ),
  )

  return {
    type: "Feature",
    properties: { incidentId: incident.incidentId, radiusMetres: radius },
    geometry: { type: "Polygon", coordinates: [ring] },
  }
}

export function projectAffectedAreas(incidents: readonly RadiusIncident[]): RadiusFeatureCollection {
  const features: RadiusFeature[] = []
  for (const incident of incidents) {
    const feature = radiusFeature(incident)
    if (feature !== null) {
      features.push(feature)
    }
  }
  return { type: "FeatureCollection", features }
}
