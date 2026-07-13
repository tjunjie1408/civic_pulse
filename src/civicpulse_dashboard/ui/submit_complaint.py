"""Live complaint submission workflow."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import cast

import streamlit as st

from civicpulse_dashboard.api_client import ApiClient
from civicpulse_dashboard.api_errors import DashboardApiError
from civicpulse_dashboard.api_models import Category, ComplaintCreateRequest
from civicpulse_dashboard.state import DashboardSessionState


def draft_fingerprint(text: str, latitude: float, longitude: float, category: str) -> str:
    """Create a stable UI-only identity for the current form draft."""

    payload = json.dumps(
        {
            "text": text,
            "latitude": latitude,
            "longitude": longitude,
            "category": category,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def render_submit_complaint(client: ApiClient, state: DashboardSessionState) -> None:
    """Render a safe form; the mutation always goes through ApiClient."""

    st.subheader("Submit a live complaint")
    st.caption("Your report is sent to the CivicPulse API and may create a new snapshot.")
    with st.form("complaint_submission"):
        text = st.text_area("Complaint", max_chars=2000, placeholder="Describe the issue")
        category = cast(
            Category,
            st.selectbox(
                "Category",
                [
                    "pothole",
                    "blocked_drain",
                    "flooding",
                    "rubbish",
                    "street_light",
                    "other",
                ],
            ),
        )
        latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=3.07)
        longitude = st.number_input(
            "Longitude", min_value=-180.0, max_value=180.0, value=101.52
        )
        submitted = st.form_submit_button("Submit complaint")

    fingerprint = draft_fingerprint(text, latitude, longitude, category)
    key = state.ensure_idempotency_key(fingerprint)
    if not submitted:
        return

    if state.submission_in_progress:
        st.info("Submission already in progress. Please wait for the API response.")
        return
    state.submission_in_progress = True
    try:
        request = ComplaintCreateRequest(
            text=text,
            latitude=latitude,
            longitude=longitude,
            reported_at=datetime.now(UTC),
            category=category,
        )
        result = client.submit_complaint(request, key)
    except DashboardApiError as exc:
        st.error(exc.user_message)
        return
    finally:
        state.submission_in_progress = False

    transition = result.incident_transition
    state.apply_mutation_transition(
        previous_ids=[str(item) for item in transition.previous_incident_snapshot_ids],
        current_ids=[str(item) for item in transition.current_incident_snapshot_ids],
    )
    try:
        refreshed = client.list_incidents(status="confirmed", limit=100)
    except DashboardApiError as exc:
        st.warning(
            "Complaint recorded, but the incident queue could not refresh: "
            f"{exc.user_message}"
        )
    else:
        st.caption(f"Incident queue refreshed from the API ({refreshed.total} snapshots).")
    st.success("Complaint replayed safely." if result.replayed else "Complaint submitted.")
    st.write("Confirmed snapshot transitions", state.last_mutation_result)
    if any(priority is None for priority in result.priorities):
        st.warning("A resulting conflict has no operational priority.")
