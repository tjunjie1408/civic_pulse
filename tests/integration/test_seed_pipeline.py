import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from civicpulse.config import load_matching_policy, load_priority_policy
from civicpulse.domain import MatchState, ReviewStatus
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService, SeedComplaint


class FakeProvider:
    model_name = "fake-model"
    normalization_version = "normalization-v1"

    def embed(self, texts):
        return tuple((1.0, 0.0) for _ in texts)


def make_service(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    return CivicPulseService(
        repository,
        load_matching_policy("config/matching_policy.json"),
        load_priority_policy("config/priority_policy.json"),
        FakeProvider(),
    ), repository


def write_seed(path: Path, *, reverse: bool = False, invalid_hash: bool = False) -> None:
    complaints = [
        {
            "seed_key": f"complaint-{index}",
            "text": "Pothole at Block A Jalan Ampang" if index % 2 else "Pothole near school",
            "latitude": 3.1390,
            "longitude": 101.6869,
            "reported_at": datetime(2026, 7, 10, 8, tzinfo=timezone.utc).isoformat(),
            "category": "pothole",
        }
        for index in range(12)
    ]
    if reverse:
        complaints.reverse()
    payload = {"complaints": complaints, "review_resolutions": []}
    canonical_payload = {
        "complaints": [
            SeedComplaint.model_validate(item).model_dump(mode="json")
            for item in sorted(complaints, key=lambda value: value["seed_key"])
        ],
        "review_resolutions": [],
    }
    content = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode()
    content_hash = hashlib.sha256(content).hexdigest()
    manifest = {
        "seed_version": "1.0.0",
        "content_sha256": ("0" * 64) if invalid_hash else content_hash,
        "normalization_version": "normalization-v1",
        "embedding_model": "fake-model",
        "embedding_dimension": 2,
        "matching_policy_version": "matching-v1",
        "priority_policy_version": "priority-v1",
    }
    path.write_text(json.dumps({"manifest": manifest, **payload}), encoding="utf-8")


def snapshot(repository: SQLiteRepository):
    return (
        repository.list_complaints(),
        repository.list_incidents(),
        repository.list_reviews(),
    )


def test_seed_import_is_repeatable_and_order_independent(tmp_path):
    service, repository = make_service(tmp_path)
    seed = tmp_path / "seed.json"
    write_seed(seed)

    first = service.initialize_seed(seed)
    first_snapshot = snapshot(repository)
    second = service.reset_seed(seed)
    second_snapshot = snapshot(repository)

    assert first == second
    assert first_snapshot == second_snapshot

    reversed_seed = tmp_path / "reversed.json"
    write_seed(reversed_seed, reverse=True)
    assert service.reset_seed(reversed_seed) == first
    assert snapshot(repository) == first_snapshot


def test_invalid_checksum_leaves_previous_database_unchanged(tmp_path):
    service, repository = make_service(tmp_path)
    valid = tmp_path / "valid.json"
    invalid = tmp_path / "invalid.json"
    write_seed(valid)
    write_seed(invalid, invalid_hash=True)
    service.initialize_seed(valid)
    before = snapshot(repository)

    with pytest.raises(ValueError, match="checksum"):
        service.reset_seed(invalid)

    assert snapshot(repository) == before


def test_model_or_policy_mismatch_fails_before_writing(tmp_path):
    service, repository = make_service(tmp_path)
    seed = tmp_path / "seed.json"
    write_seed(seed)
    payload = json.loads(seed.read_text(encoding="utf-8"))
    payload["manifest"]["embedding_model"] = "different-model"
    seed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="embedding model"):
        service.initialize_seed(seed)

    assert repository.list_complaints() == []


def write_review_seed(path: Path) -> None:
    reported_at = datetime(2026, 7, 10, 8, tzinfo=timezone.utc)
    complaints = [
        {
            "seed_key": "review-a",
            "text": "Pothole here",
            "latitude": 3.1390,
            "longitude": 101.6869,
            "reported_at": reported_at.isoformat(),
            "category": "pothole",
        },
        {
            "seed_key": "review-b",
            "text": "Road hole there",
            "latitude": 3.1391,
            "longitude": 101.6870,
            "reported_at": (reported_at + timedelta(hours=1)).isoformat(),
            "category": "pothole",
        },
        {
            "seed_key": "review-c",
            "text": "Road damage somewhere",
            "latitude": 3.1392,
            "longitude": 101.6871,
            "reported_at": (reported_at + timedelta(hours=2)).isoformat(),
            "category": "pothole",
        },
    ]
    resolutions = [
        {
            "left_seed_key": "review-a",
            "right_seed_key": "review-b",
            "final_state": MatchState.AUTO_MATCH.value,
            "reviewer_id": "seed-reviewer",
            "note": "same visible road defect",
        },
        {
            "left_seed_key": "review-b",
            "right_seed_key": "review-c",
            "final_state": MatchState.NO_MATCH.value,
            "reviewer_id": "seed-reviewer",
            "note": "separate location after inspection",
        },
    ]
    canonical_payload = {
        "complaints": [
            SeedComplaint.model_validate(item).model_dump(mode="json")
            for item in sorted(complaints, key=lambda value: value["seed_key"])
        ],
        "review_resolutions": resolutions,
    }
    content = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode()
    payload = {
        "manifest": {
            "seed_version": "review-seed-v1",
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "normalization_version": "normalization-v1",
            "embedding_model": "fake-model",
            "embedding_dimension": 2,
            "matching_policy_version": "matching-v1",
            "priority_policy_version": "priority-v1",
        },
        "complaints": complaints,
        "review_resolutions": resolutions,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_seed_restores_pending_approved_and_rejected_reviews(tmp_path):
    service, repository = make_service(tmp_path)
    seed = tmp_path / "review-seed.json"
    write_review_seed(seed)

    result = service.initialize_seed(seed)
    reviews = repository.list_reviews()

    assert result.complaint_count == 3
    assert {review.status for review in reviews} == {
        ReviewStatus.PENDING,
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
    }
    assert sum(review.final_relationship_state is MatchState.AUTO_MATCH for review in reviews) == 1
    assert sum(review.final_relationship_state is MatchState.NO_MATCH for review in reviews) == 1


def test_seed_replacement_rolls_back_when_storage_fails(tmp_path):
    service, repository = make_service(tmp_path)
    seed = tmp_path / "seed.json"
    write_seed(seed)
    service.initialize_seed(seed)
    before = snapshot(repository)

    def fail_after_complaints(point: str) -> None:
        if point == "after_seed_complaints":
            raise RuntimeError("injected seed failure")

    repository.failure_hook = fail_after_complaints
    with pytest.raises(RuntimeError, match="injected seed failure"):
        service.reset_seed(seed)

    assert snapshot(repository) == before


def test_seed_replacement_rolls_back_after_dataset_delete(tmp_path):
    service, repository = make_service(tmp_path)
    seed = tmp_path / "seed.json"
    write_seed(seed)
    service.initialize_seed(seed)
    extra = repository.list_complaints()[0].model_copy(
        update={"id": UUID("00000000-0000-0000-0000-000000000999")}
    )
    repository.add_complaint(extra, "recovery-key")
    before = storage_snapshot(repository)

    def fail_after_delete(point: str) -> None:
        if point == "after_dataset_delete":
            raise RuntimeError("injected dataset delete failure")

    repository.failure_hook = fail_after_delete
    with pytest.raises(RuntimeError, match="injected dataset delete failure"):
        service.reset_seed(seed)

    assert storage_snapshot(repository) == before


def storage_snapshot(repository):
    tables = (
        "complaints",
        "embeddings",
        "incidents",
        "incident_members",
        "match_edges",
        "submission_keys",
        "reviews",
    )
    with repository.connect() as connection:
        return tuple(
            (
                table,
                tuple(tuple(row) for row in connection.execute(f"SELECT * FROM {table}").fetchall()),
            )
            for table in tables
        )


def test_malformed_seed_leaves_previous_database_unchanged(tmp_path):
    service, repository = make_service(tmp_path)
    valid = tmp_path / "valid.json"
    malformed = tmp_path / "malformed.json"
    write_seed(valid)
    service.initialize_seed(valid)
    before = snapshot(repository)

    payload = json.loads(valid.read_text(encoding="utf-8"))
    del payload["complaints"][0]["text"]
    malformed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid seed"):
        service.reset_seed(malformed)

    assert snapshot(repository) == before
