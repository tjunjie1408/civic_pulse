import type {
  IncidentListPort,
  IncidentListQuery,
  IncidentListResult,
} from "../../application/incident-list-port"
import { decodeIncidentList } from "./decode-incident-list"

interface IncidentListHttpAdapterDependencies {
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

export class IncidentListHttpAdapter implements IncidentListPort {
  constructor(private readonly dependencies: IncidentListHttpAdapterDependencies) {}

  async list(query: IncidentListQuery, signal: AbortSignal): Promise<IncidentListResult> {
    let response: Response
    try {
      response = await this.dependencies.fetch(
        `${this.dependencies.baseUrl}/incidents?limit=${query.limit}&offset=${query.offset}`,
        { method: "GET", signal },
      )
    } catch (error: unknown) {
      return {
        ok: false,
        error: { kind: isAbortError(error) ? "aborted" : "network" },
      }
    }

    if (!response.ok) {
      return { ok: false, error: { kind: "service", status: response.status } }
    }

    try {
      const value: unknown = await response.json()
      return { ok: true, page: decodeIncidentList(value) }
    } catch (error: unknown) {
      return {
        ok: false,
        error: { kind: isAbortError(error) ? "aborted" : "contract" },
      }
    }
  }
}
