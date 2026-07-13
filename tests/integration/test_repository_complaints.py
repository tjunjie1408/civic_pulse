from datetime import datetime, timezone
from uuid import UUID

import pytest

from civicpulse.domain import Category, Complaint
from civicpulse.repository import SQLiteRepository


def complaint() -> Complaint:
    return Complaint(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        text="Pothole at Block A Jalan Ampang",
        normalized_text="pothole at block a jalan ampang",
        category=Category.POTHOLE,
        latitude=3.1390,
        longitude=101.6869,
        reported_at=datetime(2026, 7, 12, 8, tzinfo=timezone.utc),
    )


def test_add_replay_and_timezone_round_trip(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    first = repository.add_complaint(complaint(), "submission-1")
    replay = repository.add_complaint(complaint(), "submission-1")

    assert replay == first
    assert repository.list_complaints() == [first]
    assert repository.list_complaints()[0].reported_at.tzinfo is not None


def test_different_idempotency_keys_can_store_same_content(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    first = repository.add_complaint(complaint(), "submission-1")
    second = repository.add_complaint(complaint().model_copy(update={"id": UUID("00000000-0000-0000-0000-000000000002")}), "submission-2")

    assert first.text == second.text
    assert len(repository.list_complaints()) == 2


def test_embedding_vector_is_validated_and_persisted(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    item = repository.add_complaint(complaint(), "submission-1")
    repository.save_embedding(item.id, [0.1, 0.2], "test-model", "normalization-v1")

    with pytest.raises(ValueError, match="finite"):
        repository.save_embedding(item.id, [float("nan")], "test-model", "normalization-v1")
