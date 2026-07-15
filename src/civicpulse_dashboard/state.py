"""Streamlit session state that contains UI state only."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class QueueFilters:
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass
class DashboardSessionState:
    filters: QueueFilters = field(default_factory=QueueFilters)
    selected_incident_snapshot_id: str | None = None
    selected_review_id: str | None = None
    idempotency_key: str | None = None
    submission_draft_fingerprint: str | None = None
    submission_reported_at: datetime | None = None
    submission_in_progress: bool = False
    review_in_progress: bool = False
    review_note_draft: str = ""
    last_mutation_result: dict[str, Any] | None = None
    last_reset_summary: dict[str, Any] | None = None

    def clear_after_refresh(self) -> None:
        """Drop selections whose snapshot identity may have been replaced."""

        self.selected_incident_snapshot_id = None
        self.selected_review_id = None

    def business_payload(self) -> dict[str, str]:
        """Return filters only; no cached incident/review payload is retained."""

        return {
            name: value
            for name, value in (
                ("status", self.filters.status),
                ("priority", self.filters.priority),
                ("category", self.filters.category),
            )
            if value is not None
        }

    def ensure_submission_identity(
        self,
        draft_fingerprint: str,
        *,
        now: datetime | None = None,
    ) -> tuple[str, datetime]:
        """Keep one key and report time across reruns of the same draft."""

        if (
            self.submission_draft_fingerprint != draft_fingerprint
            or self.idempotency_key is None
            or self.submission_reported_at is None
        ):
            self.submission_draft_fingerprint = draft_fingerprint
            self.idempotency_key = str(uuid4())
            self.submission_reported_at = now or datetime.now(UTC)
        return self.idempotency_key, self.submission_reported_at

    def apply_mutation_transition(
        self,
        *,
        previous_ids: list[str],
        current_ids: list[str],
    ) -> None:
        """Refresh selection around membership-derived snapshot identity changes."""

        selected = self.selected_incident_snapshot_id
        self.last_mutation_result = {
            "previous_incident_snapshot_ids": list(previous_ids),
            "new_incident_snapshot_ids": list(current_ids),
        }
        if selected in previous_ids and len(current_ids) == 1:
            self.selected_incident_snapshot_id = current_ids[0]
        else:
            self.selected_incident_snapshot_id = None

    def apply_review_transition(
        self,
        *,
        review_id: str,
        previous_ids: list[str],
        current_ids: list[str],
        final_relationship_state: str,
        conflict_status: str | None,
    ) -> None:
        """Apply API-provided review transition metadata without caching payloads."""

        self.apply_mutation_transition(previous_ids=previous_ids, current_ids=current_ids)
        self.selected_review_id = review_id
        self.last_mutation_result = {
            "review_id": review_id,
            "previous_incident_snapshot_ids": list(previous_ids),
            "new_incident_snapshot_ids": list(current_ids),
            "final_relationship_state": final_relationship_state,
            "conflict_status": conflict_status,
        }

    def clear_after_reset(self) -> None:
        """Clear demo-derived UI state while preserving user filters/configuration."""

        self.selected_incident_snapshot_id = None
        self.selected_review_id = None
        self.idempotency_key = None
        self.submission_draft_fingerprint = None
        self.submission_reported_at = None
        self.submission_in_progress = False
        self.review_in_progress = False
        self.review_note_draft = ""
        self.last_mutation_result = None
        self.last_reset_summary = None


def get_session_state(session_state: MutableMapping[str, object]) -> DashboardSessionState:
    """Load or initialize dashboard state in a Streamlit-like mapping."""

    key = "_civicpulse_dashboard_state"
    current = session_state.get(key)
    if isinstance(current, DashboardSessionState):
        return current
    state = DashboardSessionState()
    session_state[key] = state
    return state
