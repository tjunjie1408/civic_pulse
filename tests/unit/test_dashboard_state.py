"""UI session state must never become a source of business truth."""

from __future__ import annotations

from datetime import UTC, datetime

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


def test_review_transition_records_snapshots_and_preserves_note_on_stale() -> None:
    state = DashboardSessionState()
    state.selected_incident_snapshot_id = "old"
    state.selected_review_id = "review-1"
    state.review_note_draft = "Keep this note"

    state.apply_review_transition(
        review_id="review-1",
        previous_ids=["old"],
        current_ids=["new"],
        final_relationship_state="auto_match",
        conflict_status=None,
    )

    assert state.selected_incident_snapshot_id == "new"
    assert state.selected_review_id == "review-1"
    assert state.review_note_draft == "Keep this note"
    assert state.last_mutation_result == {
        "review_id": "review-1",
        "previous_incident_snapshot_ids": ["old"],
        "new_incident_snapshot_ids": ["new"],
        "final_relationship_state": "auto_match",
        "conflict_status": None,
    }


def test_reset_clears_all_demo_state_but_preserves_filters() -> None:
    state = DashboardSessionState()
    state.filters.status = "pending"
    state.selected_incident_snapshot_id = "incident-1"
    state.selected_review_id = "review-1"
    state.idempotency_key = "key-1"
    state.submission_draft_fingerprint = "draft-1"
    state.submission_reported_at = datetime(2026, 7, 15, 1, tzinfo=UTC)
    state.submission_in_progress = True
    state.review_in_progress = True
    state.review_note_draft = "note"
    state.last_mutation_result = {"review_id": "review-1"}
    state.last_reset_summary = {"seed_version": "old"}

    state.clear_after_reset()

    assert state.filters.status == "pending"
    assert state.selected_incident_snapshot_id is None
    assert state.selected_review_id is None
    assert state.idempotency_key is None
    assert state.submission_draft_fingerprint is None
    assert state.submission_reported_at is None
    assert state.submission_in_progress is False
    assert state.review_in_progress is False
    assert state.review_note_draft == ""
    assert state.last_mutation_result is None
    assert state.last_reset_summary is None
