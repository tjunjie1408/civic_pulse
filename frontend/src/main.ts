import { createApp, type Component } from "vue"

import App from "./App.vue"
import { createAppServices } from "./composition/create-app-services"
import "./styles/base.css"
import "./styles/tokens.css"

const services = createAppServices()

createApp(App as Component, {
  loadIncidentQueue: services.loadIncidentQueue,
  loadIncidentDetail: services.loadIncidentDetail,
  loadReviewQueue: services.loadReviewQueue,
  loadReviewDetail: services.loadReviewDetail,
  resolveReview: services.resolveReview,
  submitComplaint: services.submitComplaint,
  createIncidentMapRenderer: services.createIncidentMapRenderer,
}).mount("#app")
