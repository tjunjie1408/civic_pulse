"""Pure UI contract tests for the protected demo reset panel."""

from __future__ import annotations

from civicpulse_dashboard.api_models import SeedResetResponse
from civicpulse_dashboard.ui.safe_reset import (
    reset_confirmation_is_valid,
    reset_enabled,
    reset_summary_rows,
)


def test_reset_is_hidden_by_default_and_requires_exact_confirmation(monkeypatch) -> None:
    monkeypatch.delenv("CIVICPULSE_DASHBOARD_SHOW_RESET", raising=False)
    assert reset_enabled() is False
    assert reset_confirmation_is_valid("RESET DEMO") is True
    assert reset_confirmation_is_valid("reset demo") is False
    assert reset_confirmation_is_valid(" RESET DEMO ") is False

    monkeypatch.setenv("CIVICPULSE_DASHBOARD_SHOW_RESET", "1")
    assert reset_enabled() is True


def test_reset_summary_rows_expose_deterministic_counts_and_checksum() -> None:
    response = SeedResetResponse.model_validate(
        {
            "seed_version": "shah-alam-demo-v1",
            "seed_checksum": "a" * 64,
            "complaint_count": 120,
            "incident_count": 60,
            "review_counts": {"pending": 4, "approved": 8, "rejected": 3},
            "priority_counts": {"low": 20, "medium": 25, "high": 12, "critical": 3},
        }
    )

    rows = reset_summary_rows(response)

    assert rows == {
        "seed_version": "shah-alam-demo-v1",
        "seed_checksum": "a" * 64,
        "complaints": 120,
        "incidents": 60,
        "reviews": {"pending": 4, "approved": 8, "rejected": 3},
        "priorities": {"low": 20, "medium": 25, "high": 12, "critical": 3},
    }
