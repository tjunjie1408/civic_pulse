"""Streamlit entrypoint for the Phase 8 dashboard."""

from __future__ import annotations

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.pages.operational_queue import render_operational_queue


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
        render_operational_queue(client)


if __name__ == "__main__":
    main()
