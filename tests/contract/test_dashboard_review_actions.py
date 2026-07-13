"""Pure UI contract tests for review resolution presentation and errors."""

from __future__ import annotations

from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import ReviewMutationResponse
from civicpulse_dashboard.state import DashboardSessionState
from civicpulse_dashboard.ui.review_queue import (
    mutation_result_rows,
    review_decision_rows,
    review_error_action,
)

from test_dashboard_review_mutations import _mutation_payload
from test_dashboard_review_reads import _detail


def test_review_decision_rows_keep_original_recommendation_separate_from_final() -> None:
    detail = _detail("00000000-0000-0000-0000-000000000003")
    detail.update(
        {
            "status": "approved",
            "resolved_at": "2026-07-13T02:00:00Z",
            "reviewer_id": "demo-officer",
            "review_note": "Same physical incident.",
            "final_relationship_state": "auto_match",
            "decision_source": "officer_review",
        }
    )
    response = ReviewMutationResponse.model_validate({**_mutation_payload(), "review": detail})

    rows = review_decision_rows(response.review)

    assert rows["original_recommendation"] == "review_required"
    assert rows["final_relationship_state"] == "auto_match"
    assert rows["decision_source"] == "officer_review"
    assert rows["reviewer_id"] == "demo-officer"


def test_conflict_result_is_presented_as_warning_with_no_priority() -> None:
    response = ReviewMutationResponse.model_validate(_mutation_payload(conflict=True))

    rows = mutation_result_rows(response)

    assert rows["presentation"] == "warning"
    assert rows["priority"] == "unavailable"
    assert "conflicted" in rows["message"]
    assert rows["previous_snapshot_ids"]
    assert rows["new_snapshot_ids"]


def test_review_error_actions_clear_or_preserve_state_without_retrying() -> None:
    state = DashboardSessionState()
    state.selected_review_id = "review-1"
    state.review_note_draft = "Keep this note"

    not_found = DashboardApiError(
        code="review_not_found", message="gone", status_code=404
    )
    assert review_error_action(state, not_found) == "refresh_queue"
    assert state.selected_review_id is None

    state.selected_review_id = "review-1"
    already_resolved = DashboardApiError(
        code="review_already_resolved", message="done", status_code=409
    )
    assert review_error_action(state, already_resolved) == "refresh_review"
    assert state.selected_review_id == "review-1"

    stale = DashboardApiError(code="review_stale", message="stale", status_code=409)
    assert review_error_action(state, stale) == "reload_and_reconfirm"
    assert state.selected_review_id == "review-1"
    assert state.review_note_draft == "Keep this note"

    transport = DashboardApiError(code="api_unreachable", message="down", status_code=0)
    assert review_error_action(state, transport) == "no_local_mutation"
