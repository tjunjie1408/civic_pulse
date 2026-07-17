"""FastAPI application factory with no import-time runtime construction."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from civicpulse.api.dto.common import ApiModel
from civicpulse.api.errors import install_error_handlers
from civicpulse.api.routes.health import router as health_router
from civicpulse.api.routes.incidents import router as incidents_router
from civicpulse.api.routes.mutations import router as mutations_router
from civicpulse.api.routes.photos import router as photos_router
from civicpulse.api.routes.reviews import router as reviews_router
from civicpulse.incident_query import IncidentQueryService
from civicpulse.photos import PhotoStore
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService, HealthReport


class AppSettings(ApiModel):
    title: str = "CivicPulse-lite API"
    version: str = "1.1.0"
    api_prefix: str = "/api/v1"
    admin_reset_enabled: bool = False
    seed_path: str = "data/seed_complaints.json"


def create_app(
    settings: AppSettings | None = None,
    *,
    service: CivicPulseService | None = None,
    repository: SQLiteRepository | None = None,
    health_service: Callable[[], HealthReport] | None = None,
    incident_query_service: IncidentQueryService | None = None,
    photo_store: PhotoStore | None = None,
) -> FastAPI:
    """Build an application around injected services without loading runtime dependencies."""
    resolved = settings or AppSettings()
    resolved_repository = repository
    if resolved_repository is None and service is not None:
        resolved_repository = getattr(service, "repository", None)
    app = FastAPI(title=resolved.title, version=resolved.version)
    app.state.service = service
    app.state.repository = resolved_repository
    app.state.health_service = health_service
    app.state.incident_query_service = incident_query_service
    app.state.photo_store = photo_store
    app.state.settings = resolved
    app.include_router(health_router, prefix=resolved.api_prefix)
    app.include_router(incidents_router, prefix=resolved.api_prefix)
    app.include_router(mutations_router, prefix=resolved.api_prefix)
    app.include_router(reviews_router, prefix=resolved.api_prefix)
    app.include_router(photos_router, prefix=resolved.api_prefix)
    install_error_handlers(app)
    return app
