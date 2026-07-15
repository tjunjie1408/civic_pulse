from pathlib import Path


def test_operational_queue_exposes_stable_performance_marker() -> None:
    source = Path("src/civicpulse_dashboard/ui/operational_queue.py").read_text(encoding="utf-8")

    assert "CivicPulse operational queue ready" in source
