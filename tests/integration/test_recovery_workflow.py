from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from civicpulse.domain import Category, Complaint
from civicpulse.repository import SQLiteRepository


def make_complaint() -> Complaint:
    return Complaint(
        id=UUID("00000000-0000-0000-0000-000000000707"),
        text="Pothole at Block A",
        normalized_text="pothole at block a",
        category=Category.POTHOLE,
        latitude=3.12,
        longitude=101.68,
        reported_at=datetime(2026, 7, 13, 1, tzinfo=UTC),
    )


def test_restart_preserves_submission_record(tmp_path: Path) -> None:
    path = tmp_path / "restart.db"
    first = SQLiteRepository(path)
    first.initialize()
    first.add_complaint(
        make_complaint(),
        "recovery-key",
        request_fingerprint="recovery-fingerprint",
    )

    restarted = SQLiteRepository(path)
    restarted.initialize()
    record = restarted.get_submission_record("recovery-key")

    assert record is not None
    assert record.request_fingerprint == "recovery-fingerprint"
    assert record.complaint.id == make_complaint().id
