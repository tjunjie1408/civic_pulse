import { IncidentListHttpAdapter } from "../features/incidents/adapters/http/incident-list-http-adapter"
import { IncidentDetailHttpAdapter } from "../features/incidents/adapters/http/incident-detail-http-adapter"
import { createMapLibreIncidentMapRenderer } from "../features/incidents/adapters/map/maplibre-map-adapter"
import type { IncidentMapRenderer } from "../features/incidents/application/incident-map-port"
import { LoadIncidentDetail } from "../features/incidents/application/load-incident-detail"
import { LoadIncidentQueue } from "../features/incidents/application/load-incident-queue"
import { ReviewHttpAdapter } from "../features/reviews/adapters/http/review-http-adapter"
import { LoadReviewDetail } from "../features/reviews/application/load-review-detail"
import { LoadReviewQueue } from "../features/reviews/application/load-review-queue"
import { ResolveReview } from "../features/reviews/application/resolve-review"

export interface AppServices {
  readonly loadIncidentQueue: LoadIncidentQueue
  readonly loadIncidentDetail: LoadIncidentDetail
  readonly loadReviewQueue: LoadReviewQueue
  readonly loadReviewDetail: LoadReviewDetail
  readonly resolveReview: ResolveReview
  readonly createIncidentMapRenderer: () => IncidentMapRenderer
}

export function createAppServices(): AppServices {
  const incidentList = new IncidentListHttpAdapter({
    baseUrl: "/api/v1",
    fetch: window.fetch.bind(window),
  })
  const incidentDetail = new IncidentDetailHttpAdapter({
    baseUrl: "/api/v1",
    fetch: window.fetch.bind(window),
  })
  const reviews = new ReviewHttpAdapter({
    baseUrl: "/api/v1",
    fetch: window.fetch.bind(window),
  })

  return {
    loadIncidentQueue: new LoadIncidentQueue(incidentList),
    loadIncidentDetail: new LoadIncidentDetail(incidentDetail),
    loadReviewQueue: new LoadReviewQueue(reviews),
    loadReviewDetail: new LoadReviewDetail(reviews),
    resolveReview: new ResolveReview(reviews),
    createIncidentMapRenderer: () => createMapLibreIncidentMapRenderer({}),
  }
}
