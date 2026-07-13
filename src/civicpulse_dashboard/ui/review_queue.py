"""Review queue, matcher evidence, and safe resolution actions."""

from __future__ import annotations

import os

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import (
    ReviewDetailResponse,
    ReviewListResponse,
    ReviewMutationResponse,
)
from civicpulse_dashboard.state import DashboardSessionState


def review_rows(page: ReviewListResponse) -> list[dict[str, str]]:
    """Project the API's review order without applying a second sort."""

    return [
        {
            "review_id": str(review.review_id),
            "status": review.status,
            "recommendation": review.original_matcher_recommendation,
            "created_at": review.created_at.isoformat().replace("+00:00", "Z"),
            "reviewer_id": review.reviewer_id or "Unassigned",
        }
        for review in page.items
    ]


def review_decision_rows(detail: ReviewDetailResponse) -> dict[str, str]:
    """Keep immutable matcher recommendation separate from officer outcome."""

    return {
        "original_recommendation": detail.original_matcher_recommendation,
        "final_relationship_state": detail.final_relationship_state or "pending",
        "decision_source": detail.decision_source or "matcher",
        "reviewer_id": detail.reviewer_id or "Unassigned",
        "resolved_at": detail.resolved_at.isoformat() if detail.resolved_at else "Unresolved",
        "review_note": detail.review_note or "No note",
    }


def mutation_result_rows(response: ReviewMutationResponse) -> dict[str, object]:
    """Project API mutation results without deriving a new business decision."""

    is_conflict = response.conflict_status == "conflict"
    return {
        "presentation": "warning" if is_conflict else "success",
        "message": (
            "Review was recorded, but the resulting incident graph is conflicted."
            if is_conflict
            else "Review resolution recorded."
        ),
        "priority": "unavailable"
        if is_conflict or any(priority is None for priority in response.resulting_priorities)
        else "available",
        "previous_snapshot_ids": [str(item) for item in response.previous_incident_snapshot_ids],
        "new_snapshot_ids": [str(item) for item in response.new_incident_snapshot_ids],
    }


def review_error_action(state: DashboardSessionState, error: DashboardApiError) -> str:
    """Apply only selection metadata for known review errors; never retry a mutation."""

    if error.code == "review_not_found":
        state.selected_review_id = None
        return "refresh_queue"
    if error.code == "review_already_resolved":
        return "refresh_review"
    if error.code == "review_stale":
        return "reload_and_reconfirm"
    return "no_local_mutation"


def render_review_detail(
    client: ApiClient,
    state: DashboardSessionState,
    review_id: str,
) -> None:
    """Read and render original matcher evidence for one review."""

    try:
        detail = client.get_review(review_id)
    except DashboardApiError as exc:
        review_error_action(state, exc)
        st.error(exc.user_message)
        if exc.code == "review_stale":
            st.warning("Reload the latest evidence before confirming this decision again.")
        return

    st.subheader("Review evidence")
    st.caption(f"Review ID: {detail.review_id} · Graph: {detail.graph_version}")
    st.write(f"Status: {detail.status}")

    left, right = st.columns(2)
    with left:
        st.markdown("**Complaint A**")
        st.write(detail.complaint_a.text)
        st.caption(f"{detail.complaint_a.category} · {detail.complaint_a.reported_at.isoformat()}")
    with right:
        st.markdown("**Complaint B**")
        st.write(detail.complaint_b.text)
        st.caption(f"{detail.complaint_b.category} · {detail.complaint_b.reported_at.isoformat()}")

    st.write(f"Original recommendation: {detail.original_matcher_recommendation}")
    st.write("Matcher reasons", detail.matcher_reasons)
    evidence = detail.matcher_evidence
    if evidence is None:
        st.info("No matcher evidence was recorded for this review.")
    else:
        first, second, third, fourth = st.columns(4)
        first.metric("Semantic similarity", f"{evidence.semantic_similarity:.2f}")
        second.metric("Geo distance", f"{evidence.geo_distance_metres:.0f} m")
        third.metric("Time difference", f"{evidence.time_difference_seconds / 3600:.1f} h")
        fourth.metric("Category", "Compatible" if evidence.category_compatibility else "Different")
        st.write(f"Location compatibility: {evidence.location_compatibility}")
        st.write(
            "Location entities",
            [
                f"{item.kind}: {item.value}"
                for item in evidence.first_location_entities + evidence.second_location_entities
            ],
        )

    if detail.resolved_at is not None:
        rows = review_decision_rows(detail)
        st.write(f"Resolved at: {rows['resolved_at']}")
        st.write(f"Reviewer: {rows['reviewer_id']}")
        st.write(f"Final relationship: {rows['final_relationship_state']}")
        st.write(f"Decision source: {rows['decision_source']}")
        st.write(f"Review note: {rows['review_note']}")
    else:
        st.info("This review is pending officer resolution.")
        _render_resolution_actions(client, state, detail)


def _render_resolution_actions(
    client: ApiClient,
    state: DashboardSessionState,
    detail: ReviewDetailResponse,
) -> None:
    reviewer_id = st.text_input(
        "Reviewer ID",
        value=os.getenv("CIVICPULSE_REVIEWER_ID", "demo-officer"),
        max_chars=120,
    )
    note = st.text_area("Review note (optional)", value=state.review_note_draft, max_chars=1000)
    state.review_note_draft = note
    approve_confirmed = st.checkbox("I confirm this relationship should be approved.")
    reject_confirmed = st.checkbox("I confirm this relationship should be rejected.")
    disabled = state.review_in_progress or not reviewer_id.strip()
    approve, reject = st.columns(2)
    with approve:
        if st.button("Approve relationship", disabled=disabled or not approve_confirmed):
            _resolve_review(client, state, detail.review_id, reviewer_id, note, approve=True)
    with reject:
        if st.button("Reject relationship", disabled=disabled or not reject_confirmed):
            _resolve_review(client, state, detail.review_id, reviewer_id, note, approve=False)


def _resolve_review(
    client: ApiClient,
    state: DashboardSessionState,
    review_id: object,
    reviewer_id: str,
    note: str,
    *,
    approve: bool,
) -> None:
    state.review_in_progress = True
    try:
        resolver = client.approve_review if approve else client.reject_review
        response = resolver(str(review_id), reviewer_id, note or None)
    except DashboardApiError as exc:
        review_error_action(state, exc)
        st.error(exc.user_message)
        if exc.code == "review_stale":
            st.warning("The note was kept. Reload the evidence and confirm again.")
        return
    finally:
        state.review_in_progress = False

    state.apply_review_transition(
        review_id=str(response.review.review_id),
        previous_ids=[str(item) for item in response.previous_incident_snapshot_ids],
        current_ids=[str(item) for item in response.new_incident_snapshot_ids],
        final_relationship_state=response.final_relationship_state,
        conflict_status=response.conflict_status,
    )
    state.review_note_draft = ""
    rows = mutation_result_rows(response)
    if rows["presentation"] == "warning":
        st.warning(str(rows["message"]))
        st.write("Operational priority is unavailable for this conflicted result.")
    else:
        st.success(str(rows["message"]))
    st.write("Previous incident snapshots", rows["previous_snapshot_ids"])
    st.write("New incident snapshots", rows["new_snapshot_ids"])


def render_review_queue(client: ApiClient, state: DashboardSessionState) -> None:
    """Render the API-backed review queue and selected detail."""

    st.subheader("Review queue")
    selected_status = st.selectbox(
        "Review status",
        options=[None, "pending", "approved", "rejected"],
        format_func=lambda value: "All reviews" if value is None else value.title(),
    )
    page = _load_reviews(client, selected_status)
    if page is None:
        return
    if not page.items:
        st.info("No reviews match the current status filter.")
        return

    st.write(f"Showing {len(page.items)} of {page.total} reviews")
    st.table(review_rows(page))  # pyright: ignore[reportUnknownMemberType]
    review_ids = [str(review.review_id) for review in page.items]
    current_index = (
        review_ids.index(state.selected_review_id)
        if state.selected_review_id in review_ids
        else 0
    )
    selected_review = st.selectbox("Open review", options=review_ids, index=current_index)
    state.selected_review_id = selected_review
    render_review_detail(client, state, state.selected_review_id)


def _load_reviews(client: ApiClient, status: str | None) -> ReviewListResponse | None:
    try:
        return client.list_reviews(status=status)
    except DashboardApiError as exc:
        st.error(exc.user_message)
        return None
