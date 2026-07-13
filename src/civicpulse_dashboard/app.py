"""Streamlit entrypoint for the Phase 8 dashboard."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import cast

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.state import get_session_state
from civicpulse_dashboard.ui.operational_queue import render_operational_queue
from civicpulse_dashboard.ui.review_queue import render_review_queue


def main() -> None:
    st.set_page_config(page_title="CivicPulse operations", page_icon="📍", layout="wide")
    with ApiClient() as client:
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
        state = get_session_state(cast(MutableMapping[str, object], st.session_state))
        incident_tab, review_tab = st.tabs(["Incidents", "Reviews"])
        with incident_tab:
            render_operational_queue(client)
        with review_tab:
            render_review_queue(client, state)


if __name__ == "__main__":
    main()
