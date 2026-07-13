from datetime import datetime, timezone

import pytest

from civicpulse.config import load_matching_policy, load_priority_policy
from civicpulse.domain import Category, ComplaintInput, MatchState, ReviewStatus
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService, IdempotencyConflict


class FakeProvider:
    model_name = "fake-model"
    normalization_version = "normalization-v1"

    def embed(self, texts):
        return tuple((1.0, 0.0) for _ in texts)


NOW = datetime.now(timezone.utc).replace(microsecond=0)


def payload(text: str, *, category: Category | None = Category.POTHOLE) -> ComplaintInput:
    return ComplaintInput(
        text=text,
        category=category,
        latitude=3.1390,
        longitude=101.6869,
        reported_at=NOW,
    )


def service(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    return CivicPulseService(
        repository,
        load_matching_policy("config/matching_policy.json"),
        load_priority_policy("config/priority_policy.json"),
        FakeProvider(),
    ), repository


def test_first_submission_creates_isolated_incident(tmp_path):
    application, repository = service(tmp_path)

    result = application.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)

    assert result.created is True
    assert result.incident.report_count == 1
    assert result.priority.confirmed_report_count == 1
    assert len(repository.list_complaints()) == 1


def test_clear_second_submission_auto_matches_and_increments_confirmed_count(tmp_path):
    application, _ = service(tmp_path)
    application.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)

    result = application.submit_complaint(payload("Road hole at Blok A Jln Ampang"), "two", now=NOW)

    assert result.incident.report_count == 2
    assert result.incident.confirmed_edges[0].decision is MatchState.AUTO_MATCH
    assert result.priority.confirmed_report_count == 2


def test_ambiguous_submission_is_review_candidate_and_does_not_join_confirmed_incident(tmp_path):
    application, repository = service(tmp_path)
    first = application.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)

    result = application.submit_complaint(
        payload("Pothole near school", category=Category.POTHOLE), "two", now=NOW
    )

    assert result.incident.report_count == 1
    assert result.incident.review_candidate_ids == (first.complaint.id,)
    assert len(repository.list_complaints()) == 2


def test_replaying_idempotency_key_does_not_create_duplicate(tmp_path):
    application, repository = service(tmp_path)
    first = application.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)

    replay = application.submit_complaint(payload(" Pothole at Block A Jalan Ampang "), "one", now=NOW)

    assert replay.created is False
    assert replay.complaint.id == first.complaint.id
    assert len(repository.list_complaints()) == 1


def test_reusing_idempotency_key_with_different_payload_is_rejected(tmp_path):
    application, repository = service(tmp_path)
    application.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)

    with pytest.raises(IdempotencyConflict):
        application.submit_complaint(payload("Different pothole at Block B"), "one", now=NOW)

    assert len(repository.list_complaints()) == 1


def test_idempotency_replay_preserves_original_transition_after_restart(tmp_path):
    application, repository = service(tmp_path)
    first = application.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)
    restarted = CivicPulseService(
        repository,
        load_matching_policy("config/matching_policy.json"),
        load_priority_policy("config/priority_policy.json"),
        FakeProvider(),
    )

    replay = restarted.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)

    assert replay.created is False
    assert replay.complaint.id == first.complaint.id
    assert replay.previous_incident_ids == first.previous_incident_ids
    assert replay.current_incident_ids == first.current_incident_ids
    assert replay.incident == first.incident
    assert len(repository.list_complaints()) == 1


def test_review_resolution_preserves_original_matcher_evidence(tmp_path):
    application, repository = service(tmp_path)
    first = application.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)
    application.submit_complaint(payload("Pothole near school", category=Category.POTHOLE), "two", now=NOW)
    stored = repository.list_reviews()[0]

    result = application.resolve_review(stored.review_id, approve=True, reviewer_id="demo-officer", now=NOW)

    assert stored.status is ReviewStatus.PENDING
    assert stored.matcher_evidence is not None
    assert result.review.status is ReviewStatus.APPROVED
    assert result.review.matcher_evidence == stored.matcher_evidence
    assert result.previous_incident_ids
    assert result.new_incident_ids
    assert first.complaint.id in result.affected_complaint_ids


def test_resolved_review_persists_across_application_restart(tmp_path):
    application, repository = service(tmp_path)
    application.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)
    application.submit_complaint(payload("Pothole near school", category=Category.POTHOLE), "two", now=NOW)
    stored = repository.list_reviews()[0]
    application.resolve_review(stored.review_id, approve=False, reviewer_id="demo-officer", now=NOW)

    restarted, _ = service(tmp_path)
    read = restarted.get_review(stored.review_id)

    assert read is not None
    assert read.review.status is ReviewStatus.REJECTED
    assert read.review.resolved_at == NOW
    assert read.review.matcher_evidence == stored.matcher_evidence
