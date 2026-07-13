"""Review queue and read-only review detail view."""

from __future__ import annotations

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import ReviewListResponse
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


def render_review_detail(
    client: ApiClient,
    state: DashboardSessionState,
    review_id: str,
) -> None:
    """Read and render original matcher evidence for one review."""

    try:
        detail = client.get_review(review_id)
    except DashboardApiError as exc:
        if exc.code == "review_not_found":
            state.selected_review_id = None
        st.error(exc.user_message)
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
        st.write(f"Resolved at: {detail.resolved_at.isoformat()}")
        st.write(f"Reviewer: {detail.reviewer_id or 'Unknown'}")
        st.write(f"Final relationship: {detail.final_relationship_state or 'Not recorded'}")
        if detail.review_note:
            st.write(f"Review note: {detail.review_note}")
    else:
        st.info("This review is pending. Resolution actions will be added in Task 8.4.")


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
