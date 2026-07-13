"""UI session state must never become a source of business truth."""

from __future__ import annotations

from civicpulse_dashboard.state import DashboardSessionState


def test_state_keeps_only_selection_filters_and_mutation_metadata() -> None:
    state = DashboardSessionState()
    state.selected_incident_snapshot_id = "snapshot-1"
    state.selected_review_id = "review-1"
    state.idempotency_key = "key-1"
    state.last_mutation_result = {"new_incident_snapshot_ids": ["snapshot-2"]}

    state.clear_after_refresh()

    assert state.selected_incident_snapshot_id is None
    assert state.selected_review_id is None
    assert state.idempotency_key == "key-1"
    assert state.last_mutation_result is not None


def test_state_filter_changes_do_not_store_incident_or_review_payloads() -> None:
    state = DashboardSessionState()
    state.filters.status = "confirmed"
    state.filters.priority = "high"
    state.filters.category = "pothole"

    assert state.business_payload() == {
        "status": "confirmed",
        "priority": "high",
        "category": "pothole",
    }
