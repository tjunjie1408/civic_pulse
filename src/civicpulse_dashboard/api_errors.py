"""Safe, user-facing error types for the dashboard HTTP boundary."""

from __future__ import annotations

from typing import Any

_USER_MESSAGES = {
    "api_unreachable": "Core service is unavailable. Check that the API is running.",
    "api_contract_error": "The API returned an unexpected response. Refresh and try again.",
    "readiness_failure": "Core service is not ready. Check the model cache and database.",
    "incident_not_found": (
        "This incident snapshot has changed. Refreshing the queue may show its successor."
    ),
    "review_not_found": "This review is no longer available. Refresh the review queue.",
    "review_already_resolved": "This review was already handled. Refresh the page.",
    "review_stale": "The review evidence is stale. Reload it and confirm the decision again.",
    "idempotency_conflict": "This submission key was already used with different complaint data.",
    "validation_error": "Check the submitted fields and try again.",
    "admin_reset_disabled": "Demo reset is disabled by the API configuration.",
}


class DashboardApiError(Exception):
    """A sanitized API failure suitable for conversion into a UI message."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.user_message = _USER_MESSAGES.get(code, self._status_message())
        super().__init__(self.user_message)

    def _status_message(self) -> str:
        if self.status_code == 404:
            return "The requested resource was not found. Refresh and try again."
        if self.status_code == 409:
            return (
                "The requested change conflicts with the current server state. "
                "Refresh and try again."
            )
        if self.status_code == 422:
            return "The request could not be validated. Check the submitted fields."
        if self.status_code == 503:
            return "Core service is temporarily unavailable. Check its readiness status."
        if self.status_code >= 500:
            return "Core service failed to complete the request. Try again later."
        return "The API request could not be completed."


ApiError = DashboardApiError
