import type { IncidentListPort, IncidentListResult } from "./incident-list-port"

export class LoadIncidentQueue {
  constructor(private readonly port: IncidentListPort) {}

  execute(signal: AbortSignal): Promise<IncidentListResult> {
    return this.port.list({ limit: 100, offset: 0 }, signal)
  }
}
