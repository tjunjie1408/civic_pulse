"""Generate the deterministic 120-record CivicPulse demo seed."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from civicpulse.demo_seed import build_seed_complaints
from civicpulse.service import SeedComplaint


def main() -> None:
    complaints = build_seed_complaints()
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
            "seed_version": "shah-alam-demo-v1",
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
