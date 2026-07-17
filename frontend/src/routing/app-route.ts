import { onScopeDispose, readonly, ref } from "vue"
import type { Ref } from "vue"

export type AppRoute =
  | { readonly kind: "queue" }
  | { readonly kind: "incident-detail"; readonly snapshotId: string }

export interface AppRouteController {
  readonly route: Readonly<Ref<AppRoute>>
  readonly notice: Readonly<Ref<string | null>>
  readonly openIncident: (snapshotId: string) => void
  readonly returnToQueue: (notice?: string | null) => void
}

const INCIDENT_ROUTE_PREFIX = "/incidents/"

export function parseAppRoute(pathname: string): AppRoute {
  if (!pathname.startsWith(INCIDENT_ROUTE_PREFIX)) {
    return { kind: "queue" }
  }

  const encodedSnapshotId = pathname.slice(INCIDENT_ROUTE_PREFIX.length).replace(/\/$/, "")
  if (encodedSnapshotId.length === 0 || encodedSnapshotId.includes("/")) {
    return { kind: "queue" }
  }

  try {
    const snapshotId = decodeURIComponent(encodedSnapshotId)
    return snapshotId.length === 0
      ? { kind: "queue" }
      : { kind: "incident-detail", snapshotId }
  } catch {
    return { kind: "queue" }
  }
}

export function incidentDetailPath(snapshotId: string): string {
  return `${INCIDENT_ROUTE_PREFIX}${encodeURIComponent(snapshotId)}`
}

export function useAppRoute(): AppRouteController {
  const route = ref<AppRoute>(parseAppRoute(window.location.pathname))
  const notice = ref<string | null>(null)

  const handlePopState = (): void => {
    route.value = parseAppRoute(window.location.pathname)
    notice.value = null
  }

  const navigate = (path: string, nextRoute: AppRoute): void => {
    window.history.pushState({}, "", path)
    route.value = nextRoute
  }

  const openIncident = (snapshotId: string): void => {
    notice.value = null
    navigate(incidentDetailPath(snapshotId), { kind: "incident-detail", snapshotId })
  }

  const returnToQueue = (nextNotice: string | null = null): void => {
    window.history.replaceState({}, "", "/")
    route.value = { kind: "queue" }
    notice.value = nextNotice
  }

  window.addEventListener("popstate", handlePopState)
  onScopeDispose(() => window.removeEventListener("popstate", handlePopState))

  return {
    route: readonly(route),
    notice: readonly(notice),
    openIncident,
    returnToQueue,
  }
}
