import type { IncidentDetailPort, IncidentDetailResult } from "./incident-detail-port"

export class LoadIncidentDetail {
  constructor(private readonly port: IncidentDetailPort) {}

  execute(incidentId: string, signal: AbortSignal): Promise<IncidentDetailResult> {
    return this.port.get(incidentId, signal)
  }
}
