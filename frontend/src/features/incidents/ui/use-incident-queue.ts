import { onScopeDispose, readonly, shallowRef } from "vue"
import type { ShallowRef } from "vue"

import type { IncidentListError } from "../application/incident-list-port"
import type { LoadIncidentQueue } from "../application/load-incident-queue"
import type { IncidentPage } from "../domain/incident"

export type IncidentQueueState =
  | { readonly kind: "loading"; readonly previous: IncidentPage | null }
  | { readonly kind: "ready"; readonly page: IncidentPage }
  | { readonly kind: "empty"; readonly page: IncidentPage }
  | {
      readonly kind: "failed"
      readonly previous: IncidentPage | null
      readonly error: Exclude<IncidentListError, { kind: "aborted" }>
    }

export interface IncidentQueue {
  readonly state: Readonly<ShallowRef<IncidentQueueState>>
  readonly load: () => Promise<void>
  readonly refresh: () => Promise<void>
  readonly retry: () => Promise<void>
}

export function useIncidentQueue(
  loadIncidentQueue: Pick<LoadIncidentQueue, "execute">,
): IncidentQueue {
  const state = shallowRef<IncidentQueueState>({ kind: "loading", previous: null })
  let activeController: AbortController | null = null
  let requestId = 0

  const previousPage = (): IncidentPage | null => {
    switch (state.value.kind) {
      case "ready":
      case "empty":
        return state.value.page
      case "loading":
      case "failed":
        return state.value.previous
    }
  }

  const request = async (): Promise<void> => {
    const previous = previousPage()
    activeController?.abort()

    const controller = new AbortController()
    const currentRequestId = ++requestId
    activeController = controller
    state.value = { kind: "loading", previous }

    const result = await loadIncidentQueue.execute(controller.signal)
    if (currentRequestId !== requestId || controller.signal.aborted) {
      return
    }

    activeController = null
    if (result.ok) {
      state.value = result.page.items.length === 0
        ? { kind: "empty", page: result.page }
        : { kind: "ready", page: result.page }
      return
    }

    if (result.error.kind !== "aborted") {
      state.value = { kind: "failed", previous, error: result.error }
    }
  }

  onScopeDispose(() => {
    requestId += 1
    activeController?.abort()
    activeController = null
  })

  return {
    state: readonly(state),
    load: request,
    refresh: request,
    retry: request,
  }
}
