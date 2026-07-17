import { onScopeDispose, readonly, shallowRef } from "vue"
import type { ShallowRef } from "vue"

import type { IncidentDetailError } from "../application/incident-detail-port"
import type { LoadIncidentDetail } from "../application/load-incident-detail"
import type { IncidentDetail } from "../domain/incident"

export type IncidentDetailState =
  | { readonly kind: "idle" }
  | { readonly kind: "loading"; readonly incidentId: string }
  | { readonly kind: "ready"; readonly incidentId: string; readonly detail: IncidentDetail }
  | { readonly kind: "missing"; readonly incidentId: string }
  | {
      readonly kind: "failed"
      readonly incidentId: string
      readonly error: Exclude<IncidentDetailError, { kind: "aborted" | "missing" }>
    }

export interface IncidentDetailLoader {
  readonly state: Readonly<ShallowRef<IncidentDetailState>>
  readonly load: (incidentId: string) => Promise<void>
  readonly retry: () => Promise<void>
  readonly clear: () => void
}

export function useIncidentDetail(
  loadIncidentDetail: Pick<LoadIncidentDetail, "execute">,
): IncidentDetailLoader {
  const state = shallowRef<IncidentDetailState>({ kind: "idle" })
  let activeController: AbortController | null = null
  let requestId = 0
  let currentIncidentId: string | null = null

  const load = async (incidentId: string): Promise<void> => {
    activeController?.abort()
    const controller = new AbortController()
    const currentRequestId = ++requestId
    activeController = controller
    currentIncidentId = incidentId
    state.value = { kind: "loading", incidentId }

    const result = await loadIncidentDetail.execute(incidentId, controller.signal)
    if (currentRequestId !== requestId || controller.signal.aborted) return

    activeController = null
    if (result.ok) {
      state.value = { kind: "ready", incidentId, detail: result.detail }
    } else if (result.error.kind === "missing") {
      state.value = { kind: "missing", incidentId }
    } else if (result.error.kind !== "aborted") {
      state.value = { kind: "failed", incidentId, error: result.error }
    }
  }

  const retry = (): Promise<void> =>
    currentIncidentId === null ? Promise.resolve() : load(currentIncidentId)

  const clear = (): void => {
    requestId += 1
    activeController?.abort()
    activeController = null
    currentIncidentId = null
    state.value = { kind: "idle" }
  }

  onScopeDispose(clear)

  return { state: readonly(state), load, retry, clear }
}
