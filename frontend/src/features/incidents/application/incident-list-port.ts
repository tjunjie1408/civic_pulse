import type { IncidentPage } from "../domain/incident"

export interface IncidentListQuery {
  readonly limit: number
  readonly offset: number
}

export type IncidentListError =
  | { readonly kind: "network" }
  | { readonly kind: "service"; readonly status: number }
  | { readonly kind: "contract" }
  | { readonly kind: "aborted" }

export type IncidentListResult =
  | { readonly ok: true; readonly page: IncidentPage }
  | { readonly ok: false; readonly error: IncidentListError }

export interface IncidentListPort {
  list(query: IncidentListQuery, signal: AbortSignal): Promise<IncidentListResult>
}
