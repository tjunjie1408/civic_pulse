"""Incident snapshot detail view."""

from __future__ import annotations

from typing import cast

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import IncidentDetailResponse
from civicpulse_dashboard.state import DashboardSessionState


def incident_detail_rows(detail: IncidentDetailResponse) -> dict[str, str | int]:
    """Project detail fields without deriving new ranking or business state."""

    return {
        "snapshot_id": str(detail.incident_id),
        "status": detail.status,
        "priority": (
            detail.priority.level if detail.priority is not None else "No operational priority"
        ),
        "confirmed_reports": detail.confirmed_report_count,
        "pending_candidates": detail.pending_candidate_count,
        "categories": ", ".join(detail.category_summary),
    }


def render_incident_detail(
    client: ApiClient,
    state: DashboardSessionState,
    incident_id: str,
) -> None:
    """Read and render one current incident snapshot."""

    try:
        detail = client.get_incident(incident_id)
    except DashboardApiError as exc:
        if exc.code == "incident_not_found":
            state.selected_incident_snapshot_id = None
        st.error(exc.user_message)
        return

    summary = incident_detail_rows(detail)
    st.subheader("Incident snapshot detail")
    st.caption(f"Snapshot ID: {summary['snapshot_id']}")
    if detail.status == "conflict":
        st.warning("This snapshot contains contradictory evidence and has no operational priority.")

    first, second, third = st.columns(3)
    first.metric("Confirmed reports", detail.confirmed_report_count)
    second.metric("Pending candidates", detail.pending_candidate_count)
    third.metric("Priority", cast(str, summary["priority"]))

    st.write(f"Categories: {summary['categories']}")
    st.write(
        "Reported window: "
        f"{detail.earliest_reported_at.isoformat()} → {detail.latest_reported_at.isoformat()}"
    )
    st.write("Confirmed complaint IDs", [str(item) for item in detail.complaint_ids])
    if detail.review_candidate_ids:
        st.write(
            "Pending review complaint IDs",
            [str(item) for item in detail.review_candidate_ids],
        )
    if detail.conflict_reasons:
        st.write("Conflict reasons", detail.conflict_reasons)
