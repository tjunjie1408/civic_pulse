import { IncidentListHttpAdapter } from "../features/incidents/adapters/http/incident-list-http-adapter"
import { createMapLibreIncidentMapRenderer } from "../features/incidents/adapters/map/maplibre-map-adapter"
import type { IncidentMapRenderer } from "../features/incidents/application/incident-map-port"
import { LoadIncidentQueue } from "../features/incidents/application/load-incident-queue"

export interface AppServices {
  readonly loadIncidentQueue: LoadIncidentQueue
  readonly createIncidentMapRenderer: () => IncidentMapRenderer
}

export function createAppServices(): AppServices {
  const incidentList = new IncidentListHttpAdapter({
    baseUrl: "/api/v1",
    fetch: window.fetch.bind(window),
  })

  return {
    loadIncidentQueue: new LoadIncidentQueue(incidentList),
    createIncidentMapRenderer: () => createMapLibreIncidentMapRenderer({}),
  }
}
