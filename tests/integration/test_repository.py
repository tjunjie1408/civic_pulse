import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from civicpulse.domain import Category, Complaint
from civicpulse.repository import DatabaseBusy, DatabaseCorrupt, SQLiteRepository


def make_complaint() -> Complaint:
    return Complaint(
        id=UUID("00000000-0000-0000-0000-000000000101"),
        text="Pothole at Block A",
        normalized_text="pothole at block a",
        category=Category.POTHOLE,
        latitude=3.12,
        longitude=101.68,
        reported_at=datetime(2026, 7, 13, 1, tzinfo=UTC),
    )


def test_corrupt_database_is_sanitized(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.db"
    raw = b"not a sqlite database"
    path.write_bytes(raw)

    with pytest.raises(DatabaseCorrupt) as caught:
        SQLiteRepository(path).initialize()

    assert caught.value.code == "database_corrupt"
    assert str(path) not in str(caught.value)
    assert path.read_bytes() == raw


def test_locked_write_is_bounded_and_rolls_back_without_a_partial_row(tmp_path: Path) -> None:
    path = tmp_path / "locked.db"
    repository = SQLiteRepository(path)
    repository.initialize()
    lock = sqlite3.connect(path, timeout=1)
    lock.execute("BEGIN IMMEDIATE")

    started = time.monotonic()
    try:
        with pytest.raises(DatabaseBusy) as caught:
            repository.add_complaint(make_complaint(), "locked-key")
    finally:
        lock.rollback()
        lock.close()

    assert time.monotonic() - started < 2
    assert caught.value.code == "database_busy"
    assert repository.get_by_idempotency_key("locked-key") is None


def test_connection_sets_bounded_busy_timeout(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "timeout.db")

    with repository.connect() as connection:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 250
