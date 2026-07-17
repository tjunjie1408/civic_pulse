import type {
  IncidentDetailPort,
  IncidentDetailResult,
} from "../../application/incident-detail-port"
import { decodeIncidentDetail } from "./decode-incident-detail"

interface IncidentDetailHttpAdapterDependencies {
  readonly baseUrl: string
  readonly fetch: typeof globalThis.fetch
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  )
}

export class IncidentDetailHttpAdapter implements IncidentDetailPort {
  constructor(private readonly dependencies: IncidentDetailHttpAdapterDependencies) {}

  async get(incidentId: string, signal: AbortSignal): Promise<IncidentDetailResult> {
    let response: Response
    try {
      response = await this.dependencies.fetch(
        `${this.dependencies.baseUrl}/incidents/${encodeURIComponent(incidentId)}`,
        { method: "GET", signal },
      )
    } catch (error: unknown) {
      return {
        ok: false,
        error: { kind: isAbortError(error) ? "aborted" : "network" },
      }
    }

    if (response.status === 404) {
      return { ok: false, error: { kind: "missing" } }
    }
    if (!response.ok) {
      return { ok: false, error: { kind: "service", status: response.status } }
    }

    try {
      const value: unknown = await response.json()
      return { ok: true, detail: decodeIncidentDetail(value) }
    } catch (error: unknown) {
      return {
        ok: false,
        error: { kind: isAbortError(error) ? "aborted" : "contract" },
      }
    }
  }
}
