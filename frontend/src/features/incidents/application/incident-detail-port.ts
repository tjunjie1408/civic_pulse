import type { IncidentDetail } from "../domain/incident"

export type IncidentDetailError =
  | { readonly kind: "missing" }
  | { readonly kind: "network" }
  | { readonly kind: "service"; readonly status: number }
  | { readonly kind: "contract" }
  | { readonly kind: "aborted" }

export type IncidentDetailResult =
  | { readonly ok: true; readonly detail: IncidentDetail }
  | { readonly ok: false; readonly error: IncidentDetailError }

export interface IncidentDetailPort {
  get(incidentId: string, signal: AbortSignal): Promise<IncidentDetailResult>
}
