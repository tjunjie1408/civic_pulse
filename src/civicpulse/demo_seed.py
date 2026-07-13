"""Deterministic synthetic geography for the CivicPulse dashboard demo."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

type SeedRecord = dict[str, object]


_ZONES: tuple[tuple[str, float, float, tuple[str, ...]], ...] = (
    ("Taman Seri Murni", 3.0940, 101.5050, ("rubbish", "street_light", "flooding", "pothole")),
    (
        "Seksyen Harmoni",
        3.0820,
        101.5200,
        ("blocked_drain", "pothole", "street_light", "flooding"),
    ),
    (
        "Kawasan Perindustrian Maju",
        3.0700,
        101.5480,
        ("pothole", "rubbish", "street_light", "blocked_drain"),
    ),
    (
        "Pusat Komersial Sentosa",
        3.0650,
        101.5280,
        ("rubbish", "pothole", "blocked_drain", "street_light"),
    ),
    (
        "Kampung Sungai Damai",
        3.0460,
        101.5190,
        ("flooding", "blocked_drain", "pothole", "rubbish"),
    ),
)

_ISSUES = {
    "pothole": "pothole on the access road",
    "blocked_drain": "upstream drain blockage",
    "flooding": "flooding on the low-lying road",
    "rubbish": "rubbish accumulation",
    "street_light": "street light outage",
}


def build_seed_complaints() -> list[SeedRecord]:
    """Return 120 reports arranged in five synthetic Shah Alam-inspired zones."""

    complaints: list[SeedRecord] = []
    index = 0
    for zone_index, (zone, latitude, longitude, categories) in enumerate(_ZONES):
        for cluster_index, category in enumerate(categories):
            for report_index in range(6):
                index += 1
                row = report_index // 3
                column = report_index % 3
                report_latitude = latitude + (cluster_index - 1.5) * 0.0013 + row * 0.00012
                report_longitude = longitude + (cluster_index - 1.5) * 0.0011 + column * 0.00012
                if category == "blocked_drain" and zone == "Seksyen Harmoni":
                    narrative = "upstream drain near the school access area"
                elif category == "flooding" and zone == "Kampung Sungai Damai":
                    narrative = "low-lying road downstream from the drainage channel"
                else:
                    narrative = "synthetic municipal demo location"
                complaints.append(
                    {
                        "seed_key": f"complaint-{index:03d}",
                        "text": (
                            f"Synthetic Shah Alam demo report at {zone}: "
                            f"{_ISSUES[category]} near {narrative}, report {report_index + 1}"
                        ),
                        "latitude": round(report_latitude, 6),
                        "longitude": round(report_longitude, 6),
                        "reported_at": (
                            datetime(2026, 7, 10, 8, tzinfo=UTC)
                            + timedelta(hours=zone_index * 4 + cluster_index + report_index)
                        ).isoformat().replace("+00:00", "Z"),
                        "category": category,
                    }
                )
    return complaints
