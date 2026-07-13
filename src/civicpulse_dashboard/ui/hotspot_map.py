"""Confirmed-incident projection for the dashboard map."""

from __future__ import annotations

import streamlit as st

from civicpulse_dashboard.api_models import IncidentListResponse


def hotspot_rows(page: IncidentListResponse) -> list[dict[str, str | int | float]]:
    """Project confirmed API rows without recomputing ranking or hotspot strength."""

    rows: list[dict[str, str | int | float]] = []
    for incident in page.items:
        if incident.status != "confirmed":
            continue
        rows.append(
            {
                "incident_id": str(incident.incident_id),
                "latitude": incident.centroid.latitude,
                "longitude": incident.centroid.longitude,
                "confirmed_reports": incident.confirmed_report_count,
                "pending_candidates": incident.pending_candidate_count,
                "priority": (
                    incident.priority.level
                    if incident.priority is not None
                    else "No operational priority"
                ),
            }
        )
    return rows


def render_hotspot_map(page: IncidentListResponse) -> None:
    """Render API centroids and keep pending evidence visible but separate."""

    rows = hotspot_rows(page)
    st.subheader("Confirmed incident map")
    st.caption(
        "Demo dataset — synthetic locations and complaints modelled on a Shah Alam-inspired "
        "municipal district."
    )
    if not rows:
        st.info("No confirmed incident snapshots are available for the map.")
        return
    map_rows = [{"lat": row["latitude"], "lon": row["longitude"]} for row in rows]
    st.map(map_rows, size=20)  # pyright: ignore[reportUnknownMemberType]
    st.table(rows)  # pyright: ignore[reportUnknownMemberType]
