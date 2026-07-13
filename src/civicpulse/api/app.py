"""FastAPI application factory with no import-time runtime construction."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from civicpulse.api.dto.common import ApiModel
from civicpulse.api.errors import install_error_handlers
from civicpulse.api.routes.health import router as health_router
from civicpulse.api.routes.incidents import router as incidents_router
from civicpulse.incident_query import IncidentQueryService
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService, HealthReport


class AppSettings(ApiModel):
    title: str = "CivicPulse-lite API"
    version: str = "1.0.0"
    api_prefix: str = "/api/v1"


def create_app(
    settings: AppSettings | None = None,
    *,
    service: CivicPulseService | None = None,
    repository: SQLiteRepository | None = None,
    health_service: Callable[[], HealthReport] | None = None,
    incident_query_service: IncidentQueryService | None = None,
) -> FastAPI:
    """Build an application around injected services without loading runtime dependencies."""
    resolved = settings or AppSettings()
    app = FastAPI(title=resolved.title, version=resolved.version)
    app.state.service = service
    app.state.repository = repository
    app.state.health_service = health_service
    app.state.incident_query_service = incident_query_service
    app.include_router(health_router, prefix=resolved.api_prefix)
    app.include_router(incidents_router, prefix=resolved.api_prefix)
    install_error_handlers(app)
    return app
