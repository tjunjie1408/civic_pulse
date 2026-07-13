from datetime import datetime, timezone

import pytest

from civicpulse.config import load_matching_policy, load_priority_policy
from civicpulse.domain import ComplaintInput, MatchState, ReviewStatus
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService


class FakeProvider:
    model_name = "fake-model"
    normalization_version = "normalization-v1"

    def embed(self, texts):
        return tuple((1.0, 0.0) for _ in texts)


NOW = datetime.now(timezone.utc).replace(microsecond=0)


def payload(text: str) -> ComplaintInput:
    return ComplaintInput(
        text=text,
        category=None,
        latitude=3.1390,
        longitude=101.6869,
        reported_at=NOW,
    )


def make_service(tmp_path):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    service = CivicPulseService(
        repository,
        load_matching_policy("config/matching_policy.json"),
        load_priority_policy("config/priority_policy.json"),
        FakeProvider(),
    )
    return service, repository


def create_pending_review(tmp_path):
    service, repository = make_service(tmp_path)
    service.submit_complaint(payload("Pothole at Block A Jalan Ampang"), "one", now=NOW)
    service.submit_complaint(payload("Pothole near school"), "two", now=NOW)
    review = repository.list_reviews()[0]
    return service, repository, review


def test_approve_pending_review_merges_incident_and_preserves_matcher_evidence(tmp_path):
    service, repository, review = create_pending_review(tmp_path)

    result = service.resolve_review(review.review_id, approve=True, reviewer_id="demo-officer", note="same site")

    assert result.previous_status is ReviewStatus.PENDING
    assert result.final_status is ReviewStatus.APPROVED
    assert result.final_relationship_state is MatchState.AUTO_MATCH
    assert result.previous_incident_ids
    assert result.new_incident_ids
    assert result.conflict_status is None
    assert result.resulting_priorities[0].confirmed_report_count == 2
    stored = repository.get_review(review.review_id)
    assert stored is not None
    assert stored.matcher_recommendation is MatchState.REVIEW_REQUIRED
    assert stored.matcher_reasons == review.matcher_reasons
    assert stored.decision_source.value == "officer_review"


def test_reject_pending_review_keeps_confirmed_membership_separate(tmp_path):
    service, repository, review = create_pending_review(tmp_path)
    before = repository.list_incidents()

    result = service.resolve_review(review.review_id, approve=False, reviewer_id="demo-officer")

    assert result.final_status is ReviewStatus.REJECTED
    assert result.final_relationship_state is MatchState.NO_MATCH
    after = repository.list_incidents()
    assert {incident.complaint_ids for incident in after} == {incident.complaint_ids for incident in before}
    assert all(not incident.review_candidate_ids for incident in after)
    assert repository.get_review(review.review_id).status is ReviewStatus.REJECTED


def test_duplicate_resolution_is_rejected_and_restart_preserves_review(tmp_path):
    service, repository, review = create_pending_review(tmp_path)
    service.resolve_review(review.review_id, approve=True, reviewer_id="demo-officer")

    with pytest.raises(ValueError, match="not pending"):
        service.resolve_review(review.review_id, approve=True, reviewer_id="demo-officer")

    restarted = SQLiteRepository(tmp_path / "civicpulse.db")
    restarted.initialize()
    restored = restarted.get_review(review.review_id)
    assert restored is not None
    assert restored.status is ReviewStatus.APPROVED
    assert restored.reviewed_by == "demo-officer"


def test_unknown_review_id_is_rejected(tmp_path):
    service, _, _ = create_pending_review(tmp_path)

    with pytest.raises(ValueError, match="unknown review"):
        service.resolve_review("00000000-0000-0000-0000-999999999999", approve=True, reviewer_id="demo-officer")
