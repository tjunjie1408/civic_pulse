"""Generate the deterministic 120-record CivicPulse demo seed."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from civicpulse.service import SeedComplaint


def main() -> None:
    categories = (
        ("pothole", "Pothole at Block {block} Jalan Ampang"),
        ("blocked_drain", "Longkang tersumbat dekat sekolah block {block}"),
        ("flooding", "Air naik near school after rain block {block}"),
        ("rubbish", "Sampah tidak dikutip at Taman Melur block {block}"),
        ("street_light", "Lampu jalan rosak near Block {block} Jalan Ampang"),
    )
    hotspots = ((3.1390, 101.6869), (3.1450, 101.6900), (3.1510, 101.6940))
    complaints: list[dict[str, object]] = []
    for index in range(120):
        category, template = categories[index % len(categories)]
        hotspot = hotspots[(index // 5) % len(hotspots)]
        complaints.append(
            {
                "seed_key": f"complaint-{index:03d}",
                "text": template.format(block=chr(65 + (index % 4))),
                "latitude": hotspot[0] + (index % 5) * 0.0002,
                "longitude": hotspot[1] + (index % 4) * 0.0002,
                "reported_at": "2026-07-10T08:00:00Z",
                "category": category,
            }
        )
    ordered = sorted(complaints, key=lambda item: str(item["seed_key"]))
    canonical = {
        "complaints": [
            SeedComplaint.model_validate(item).model_dump(mode="json") for item in ordered
        ],
        "review_resolutions": [],
    }
    content = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload = {
        "manifest": {
            "seed_version": "1.0.0",
            "content_sha256": sha256(content).hexdigest(),
            "normalization_version": "normalization-v1",
            "embedding_model": "intfloat/multilingual-e5-small",
            "embedding_dimension": 384,
            "matching_policy_version": "matching-v1",
            "priority_policy_version": "priority-v1",
        },
        **canonical,
    }
    Path("data/seed_complaints.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
