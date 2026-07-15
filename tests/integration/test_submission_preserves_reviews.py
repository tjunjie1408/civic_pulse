"""Later submissions must preserve officer review decisions and persist correct embeddings."""

import sqlite3
import struct
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from civicpulse.config import load_matching_policy, load_priority_policy
from civicpulse.domain import Complaint, ComplaintInput, ReviewRecord
from civicpulse.normalize import normalize_text
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService

NOW = datetime.now(UTC).replace(microsecond=0)


class FakeProvider:
    model_name = "fake-model"
    normalization_version = "normalization-v1"

    def embed(self, texts: list[str]) -> tuple[tuple[float, float], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class DistinctProvider:
    """Deterministic per-text vectors using float32-exact components."""

    model_name = "fake-model"
    normalization_version = "normalization-v1"

    def embed(self, texts: list[str]) -> tuple[tuple[float, float], ...]:
        return tuple(self._vector(text) for text in texts)

    @staticmethod
    def _vector(text: str) -> tuple[float, float]:
        seed = sha256(text.encode("utf-8")).digest()
        return (1.0, 0.5 + seed[0] / 256.0)


def payload(text: str, latitude: float = 3.1390, longitude: float = 101.6869) -> ComplaintInput:
    return ComplaintInput(
        text=text,
        category=None,
        latitude=latitude,
        longitude=longitude,
        reported_at=NOW,
    )


def make_service(
    tmp_path: Path,
    provider: FakeProvider | DistinctProvider | None = None,
) -> tuple[CivicPulseService, SQLiteRepository]:
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    service = CivicPulseService(
        repository,
        load_matching_policy("config/matching_policy.json"),
        load_priority_policy("config/priority_policy.json"),
        provider or FakeProvider(),
    )
    return service, repository


def create_pending_review(
    tmp_path: Path,
) -> tuple[CivicPulseService, SQLiteRepository, ReviewRecord]:
    service, repository = make_service(tmp_path)
    service.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)
    service.submit_complaint(payload("Pothole near school"), "two", now=NOW)
    review = repository.list_reviews()[0]
    return service, repository, review


def memberships(repository: SQLiteRepository) -> set[frozenset[UUID]]:
    return {frozenset(incident.complaint_ids) for incident in repository.list_incidents()}


def test_approved_review_survives_later_submission(tmp_path: Path) -> None:
    service, repository, review = create_pending_review(tmp_path)
    service.resolve_review(review.review_id, approve=True, reviewer_id="demo-officer", now=NOW)
    merged_pair = frozenset((review.left_id, review.right_id))
    assert merged_pair in memberships(repository)

    result = service.submit_complaint(
        payload("Rubbish pile at Taman Jaya", latitude=3.5, longitude=101.9), "three", now=NOW
    )

    after = memberships(repository)
    assert merged_pair in after, "officer-approved merge was reverted by a later submission"
    assert frozenset((result.complaint.id,)) in after
    assert all(not incident.review_candidate_ids for incident in repository.list_incidents())
    reviews = repository.list_reviews()
    assert len(reviews) == 1
    assert reviews[0].status.value == "approved"


def test_rejected_review_survives_later_submission(tmp_path: Path) -> None:
    service, repository, review = create_pending_review(tmp_path)
    service.resolve_review(review.review_id, approve=False, reviewer_id="demo-officer", now=NOW)
    assert all(not incident.review_candidate_ids for incident in repository.list_incidents())

    service.submit_complaint(
        payload("Rubbish pile at Taman Jaya", latitude=3.5, longitude=101.9), "three", now=NOW
    )

    after = memberships(repository)
    assert frozenset((review.left_id,)) in after
    assert frozenset((review.right_id,)) in after
    assert all(not incident.review_candidate_ids for incident in repository.list_incidents()), (
        "officer-rejected pair reappeared as a review candidate after a later submission"
    )
    reviews = repository.list_reviews()
    assert len(reviews) == 1
    assert reviews[0].status.value == "rejected"


def _read_embedding(database_path: Path, complaint_id: UUID) -> tuple[float, ...]:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT vector, dimension FROM embeddings WHERE complaint_id=?",
            (str(complaint_id),),
        ).fetchone()
    assert row is not None, "no embedding stored for the submitted complaint"
    payload_bytes, dimension = row
    return struct.unpack(f"<{dimension}f", payload_bytes)


def test_persisted_embedding_belongs_to_the_submitted_complaint(tmp_path: Path) -> None:
    provider = DistinctProvider()
    service, repository = make_service(tmp_path, provider)
    existing = Complaint(
        id=UUID("ffffffff-ffff-4fff-bfff-ffffffffffff"),
        text="Existing pothole report",
        normalized_text=normalize_text("Existing pothole report"),
        latitude=3.1390,
        longitude=101.6869,
        reported_at=NOW,
    )
    repository.add_complaint(existing, "seed-key", "seed-fingerprint")

    result = service.submit_complaint(payload("Blocked drain at Jalan Baru"), "new-key", now=NOW)

    candidate = result.complaint
    assert str(candidate.id) < str(existing.id), "fixture must sort after the candidate"
    stored = _read_embedding(tmp_path / "civicpulse.db", candidate.id)
    expected = provider.embed([candidate.normalized_text])[0]
    assert stored == expected, "stored embedding is not the candidate's own vector"
