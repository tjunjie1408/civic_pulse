"""Typed HTTP gateway for the Streamlit dashboard."""

from __future__ import annotations

import os
from collections.abc import Mapping
from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import ValidationError

from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import (
    ApiErrorResponse,
    HealthResponse,
    IncidentDetailResponse,
    IncidentListResponse,
    LiveResponse,
    ReviewDetailResponse,
    ReviewListResponse,
)

DEFAULT_TIMEOUT = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0)


class ApiClient:
    """The only HTTP entrypoint used by dashboard pages."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("CIVICPULSE_API_URL", "http://127.0.0.1:8000/api/v1")
        ).rstrip("/")
        configured_timeout = (
            timeout if isinstance(timeout, httpx.Timeout) else httpx.Timeout(timeout)
        )
        self.timeout = configured_timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=configured_timeout,
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def list_incidents(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        priority: str | None = None,
        category: str | None = None,
    ) -> IncidentListResponse:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        for name, value in (("status", status), ("priority", priority), ("category", category)):
            if value is not None:
                params[name] = value
        return self._get_model("/incidents", params=params, model=IncidentListResponse)

    def get_incident(self, incident_id: str) -> IncidentDetailResponse:
        return self._get_model(f"/incidents/{incident_id}", model=IncidentDetailResponse)

    def list_reviews(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ReviewListResponse:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        return self._get_model("/reviews", params=params, model=ReviewListResponse)

    def get_review(self, review_id: str) -> ReviewDetailResponse:
        return self._get_model(f"/reviews/{review_id}", model=ReviewDetailResponse)

    def health_ready(self) -> HealthResponse:
        return self._get_model("/health/ready", model=HealthResponse)

    def health_live(self) -> LiveResponse:
        return self._get_model("/health/live", model=LiveResponse)

    def _get_model[T: Any](
        self,
        path: str,
        *,
        model: type[T],
        params: Mapping[str, str | int] | None = None,
    ) -> T:
        response = self._request("GET", path, params=params)
        try:
            return model.model_validate(response.json())
        except (ValidationError, ValueError, TypeError) as exc:
            raise DashboardApiError(
                code="api_contract_error",
                message="The API response did not match the frozen contract.",
                status_code=response.status_code,
            ) from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, params=params)
        except httpx.TimeoutException as exc:
            raise DashboardApiError(
                code="api_unreachable",
                message="The API request timed out.",
                status_code=0,
            ) from exc
        except httpx.RequestError as exc:
            raise DashboardApiError(
                code="api_unreachable",
                message="The API could not be reached.",
                status_code=0,
            ) from exc

        if response.is_success:
            return response
        raise self._error_from_response(response)

    @staticmethod
    def _error_from_response(response: httpx.Response) -> DashboardApiError:
        code = "api_error"
        message = "The API request failed."
        details: dict[str, Any] = {}
        try:
            envelope = ApiErrorResponse.model_validate(response.json())
        except (ValidationError, ValueError, TypeError):
            if response.status_code == 503:
                code = "readiness_failure"
            elif response.status_code >= 500:
                code = "api_unavailable"
        else:
            code = envelope.error.code
            message = envelope.error.message
            details = envelope.error.details
        return DashboardApiError(
            code=code,
            message=message,
            status_code=response.status_code,
            details=details,
        )
