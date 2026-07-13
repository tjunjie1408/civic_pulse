"""The demo seed must tell a coherent synthetic Klang Valley story."""

from __future__ import annotations

from civicpulse.demo_seed import build_seed_complaints


def test_seed_uses_five_shah_alam_inspired_zones_and_compact_bounds() -> None:
    complaints = build_seed_complaints()

    assert len(complaints) == 120
    texts = " ".join(str(item["text"]) for item in complaints)
    for zone in (
        "Taman Seri Murni",
        "Seksyen Harmoni",
        "Kawasan Perindustrian Maju",
        "Pusat Komersial Sentosa",
        "Kampung Sungai Damai",
    ):
        assert zone in texts

    latitudes = [float(item["latitude"]) for item in complaints]
    longitudes = [float(item["longitude"]) for item in complaints]
    assert min(latitudes) >= 3.03
    assert max(latitudes) <= 3.11
    assert min(longitudes) >= 101.49
    assert max(longitudes) <= 101.56
    assert max(latitudes) - min(latitudes) >= 0.04
    assert max(longitudes) - min(longitudes) >= 0.03


def test_seed_contains_upstream_downstream_flood_story_and_local_categories() -> None:
    complaints = build_seed_complaints()

    text_by_key = {
        str(item["seed_key"]): str(item["text"]) for item in complaints
    }
    assert any("upstream drain" in text for text in text_by_key.values())
    assert any("low-lying road" in text for text in text_by_key.values())
    assert {str(item["category"]) for item in complaints} >= {
        "blocked_drain",
        "flooding",
        "pothole",
        "rubbish",
        "street_light",
    }
