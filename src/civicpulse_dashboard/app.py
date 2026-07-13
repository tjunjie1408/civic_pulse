"""Streamlit entrypoint for the Phase 8 dashboard."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import cast

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.state import get_session_state
from civicpulse_dashboard.ui.hotspot_map import render_hotspot_map
from civicpulse_dashboard.ui.operational_queue import render_operational_queue
from civicpulse_dashboard.ui.review_queue import render_review_queue
from civicpulse_dashboard.ui.safe_reset import render_safe_reset
from civicpulse_dashboard.ui.submit_complaint import render_submit_complaint


def main() -> None:
    st.set_page_config(page_title="CivicPulse operations", page_icon="📍", layout="wide")
    with ApiClient() as client:
        state = get_session_state(cast(MutableMapping[str, object], st.session_state))
        render_safe_reset(client, state)
        try:
            readiness = client.health_ready()
        except DashboardApiError as exc:
            st.error(exc.user_message)
            return
        if not readiness.core_ready:
            st.warning(
                "Core service is not ready. Incident data is unavailable until "
                "readiness checks pass."
            )
            return
        incident_tab, map_tab, submit_tab, review_tab = st.tabs(
            ["Incidents", "Map", "Submit complaint", "Reviews"]
        )
        with incident_tab:
            render_operational_queue(client)
        with map_tab:
            try:
                confirmed_page = client.list_incidents(status="confirmed", limit=100)
            except DashboardApiError as exc:
                st.error(exc.user_message)
            else:
                render_hotspot_map(confirmed_page)
        with submit_tab:
            render_submit_complaint(client, state)
        with review_tab:
            render_review_queue(client, state)


if __name__ == "__main__":
    main()
