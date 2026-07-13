"""Explicit Dashboard-only controls for the deterministic demo reset."""

from __future__ import annotations

import os

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import SeedResetResponse
from civicpulse_dashboard.state import DashboardSessionState


def reset_enabled() -> bool:
    """Return whether this Dashboard deployment should expose demo reset."""

    return os.getenv("CIVICPULSE_DASHBOARD_SHOW_RESET", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def reset_confirmation_is_valid(value: str) -> bool:
    return value == "RESET DEMO"


def reset_summary_rows(response: SeedResetResponse) -> dict[str, object]:
    return {
        "seed_version": response.seed_version,
        "seed_checksum": response.seed_checksum,
        "complaints": response.complaint_count,
        "incidents": response.incident_count,
        "reviews": dict(response.review_counts),
        "priorities": dict(response.priority_counts),
    }


def render_safe_reset(client: ApiClient, state: DashboardSessionState) -> None:
    """Render reset only when UI config allows it; API remains the final gate."""

    if not reset_enabled():
        return

    with st.sidebar.expander("Demo administration"):
        st.caption("Synthetic Shah Alam-inspired demo data only.")
        confirmation = st.text_input("Type RESET DEMO to restore the seed", max_chars=10)
        if st.button("Reset demo data", disabled=not reset_confirmation_is_valid(confirmation)):
            try:
                response = client.reset_demo()
            except DashboardApiError as exc:
                if exc.code == "admin_reset_disabled":
                    st.warning("The current deployment has demo reset disabled.")
                else:
                    st.error(exc.user_message)
            else:
                state.clear_after_reset()
                state.last_reset_summary = reset_summary_rows(response)
                st.success("Demo data restored. Reloading health, incidents, and reviews.")
                st.rerun()

        if state.last_reset_summary is not None:
            st.write("Last reset summary", state.last_reset_summary)
