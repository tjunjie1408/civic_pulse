import { IncidentListHttpAdapter } from "../features/incidents/adapters/http/incident-list-http-adapter"
import { LoadIncidentQueue } from "../features/incidents/application/load-incident-queue"

export interface AppServices {
  readonly loadIncidentQueue: LoadIncidentQueue
}

export function createAppServices(): AppServices {
  const incidentList = new IncidentListHttpAdapter({
    baseUrl: "/api/v1",
    fetch: window.fetch.bind(window),
  })

  return {
    loadIncidentQueue: new LoadIncidentQueue(incidentList),
  }
}
