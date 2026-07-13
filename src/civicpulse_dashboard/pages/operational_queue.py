"""API-ranked operational queue page."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import cast

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import IncidentListResponse
from civicpulse_dashboard.state import get_session_state


def queue_rows(page: IncidentListResponse) -> list[dict[str, str | int]]:
    """Project the API's existing order into display rows without re-ranking."""

    rows: list[dict[str, str | int]] = []
    for incident in page.items:
        rows.append(
            {
                "incident_id": str(incident.incident_id),
                "status": incident.status,
                "priority": (
                    incident.priority.level
                    if incident.priority is not None
                    else "No operational priority"
                ),
                "confirmed_reports": incident.confirmed_report_count,
                "pending_candidates": incident.pending_candidate_count,
                "categories": ", ".join(incident.category_summary),
                "latest_reported_at": incident.latest_reported_at.isoformat().replace(
                    "+00:00", "Z"
                ),
            }
        )
    return rows


def render_operational_queue(client: ApiClient) -> None:
    """Render the queue using only data returned by the typed gateway."""

    state = get_session_state(cast(MutableMapping[str, object], st.session_state))
    st.title("Operational incident queue")
    st.caption("Ordered by the CivicPulse API. The dashboard does not recalculate priority.")

    with st.sidebar:
        st.header("Filters")
        state.filters.status = st.selectbox(
            "Status",
            options=[None, "confirmed", "isolated", "conflict"],
            format_func=lambda value: "All statuses" if value is None else value.title(),
            index=(
                0
                if state.filters.status is None
                else ["confirmed", "isolated", "conflict"].index(state.filters.status) + 1
            ),
        )
        state.filters.priority = st.selectbox(
            "Priority",
            options=[None, "critical", "high", "medium", "low", "review_required"],
            format_func=lambda value: (
                "All priorities" if value is None else value.replace("_", " ").title()
            ),
            index=(
                0
                if state.filters.priority is None
                else ["critical", "high", "medium", "low", "review_required"].index(
                    state.filters.priority
                )
                + 1
            ),
        )
        state.filters.category = st.selectbox(
            "Category",
            options=[
                None,
                "pothole",
                "blocked_drain",
                "flooding",
                "rubbish",
                "street_light",
                "other",
            ],
            format_func=lambda value: (
                "All categories" if value is None else value.replace("_", " ").title()
            ),
            index=(
                0
                if state.filters.category is None
                else [
                    "pothole",
                    "blocked_drain",
                    "flooding",
                    "rubbish",
                    "street_light",
                    "other",
                ].index(state.filters.category)
                + 1
            ),
        )

    try:
        page = client.list_incidents(
            **state.business_payload(), limit=state.filters.limit, offset=state.filters.offset
        )
    except DashboardApiError as exc:
        st.error(exc.user_message)
        return

    if not page.items:
        st.info("No incident snapshots match the current filters.")
        return

    st.write(f"Showing {len(page.items)} of {page.total} incident snapshots")
    st.table(queue_rows(page))  # pyright: ignore[reportUnknownMemberType]
