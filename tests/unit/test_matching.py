from datetime import datetime, timedelta, timezone

import pytest

from civicpulse.config import load_matching_policy
from civicpulse.domain import Category, Complaint, LocationCompatibility, MatchDecision, MatchState
from civicpulse.matching import match_pair


POLICY = load_matching_policy("config/matching_policy.json")
NOW = datetime(2026, 7, 12, 8, tzinfo=timezone.utc)


def complaint(
    category: Category,
    *,
    text: str = "Pothole at Block A Jalan Ampang",
    lat: float = 3.1390,
    lon: float = 101.6869,
    at: datetime = NOW,
) -> Complaint:
    return Complaint(
        text=text,
        normalized_text=text.casefold(),
        latitude=lat,
        longitude=lon,
        reported_at=at,
        category=category,
    )


def test_all_constraints_pass_returns_auto_match():
    decision = match_pair(
        complaint(Category.POTHOLE),
        complaint(Category.POTHOLE),
        POLICY.strong_entity_semantic_threshold,
        POLICY,
    )

    assert isinstance(decision, MatchDecision)
    assert decision.auto_match is True
    assert decision.decision is MatchState.AUTO_MATCH
    assert decision.review_required is False
    assert decision.category_compatible is True
    assert decision.location_compatibility is LocationCompatibility.COMPATIBLE


def test_known_category_mismatch_rejects_before_semantic_score():
    decision = match_pair(complaint(Category.POTHOLE), complaint(Category.STREET_LIGHT), 0.99, POLICY)

    assert decision.auto_match is False
    assert decision.review_required is False
    assert decision.decision is MatchState.NO_MATCH
    assert decision.category_compatible is False
    assert any("category mismatch" in reason for reason in decision.reasons)


def test_other_category_requires_review_without_auto_merge():
    decision = match_pair(complaint(Category.OTHER), complaint(Category.OTHER), 0.99, POLICY)

    assert decision.auto_match is False
    assert decision.review_required is True
    assert decision.decision is MatchState.REVIEW_REQUIRED
    assert decision.category_compatible is False
    assert "category requires officer review" in decision.reasons


def test_distance_and_time_constraints_reject_boundary_failures():
    far = complaint(Category.POTHOLE, lat=3.1500)
    old = complaint(Category.POTHOLE, at=NOW - timedelta(days=8))

    far_decision = match_pair(complaint(Category.POTHOLE), far, 0.99, POLICY)
    old_decision = match_pair(complaint(Category.POTHOLE), old, 0.99, POLICY)

    assert far_decision.auto_match is False
    assert far_decision.decision is MatchState.NO_MATCH
    assert any("distance" in reason for reason in far_decision.reasons)
    assert old_decision.auto_match is False
    assert old_decision.decision is MatchState.NO_MATCH
    assert any("time gap" in reason for reason in old_decision.reasons)


def test_similarity_equal_threshold_passes_and_below_threshold_rejects():
    equal = match_pair(
        complaint(Category.POTHOLE),
        complaint(Category.POTHOLE),
        POLICY.strong_entity_semantic_threshold,
        POLICY,
    )
    below = match_pair(
        complaint(Category.POTHOLE),
        complaint(Category.POTHOLE),
        POLICY.strong_entity_semantic_threshold - 0.01,
        POLICY,
    )

    assert equal.auto_match is True
    assert equal.decision is MatchState.AUTO_MATCH
    assert below.auto_match is False
    assert below.decision is MatchState.REVIEW_REQUIRED
    assert any("semantic similarity" in reason for reason in below.reasons)


def test_similarity_out_of_range_is_rejected_by_domain_contract():
    with pytest.raises(ValueError, match="similarity"):
        match_pair(complaint(Category.POTHOLE), complaint(Category.POTHOLE), 1.1, POLICY)


def test_conflicting_explicit_location_is_no_match_even_when_semantics_are_high():
    decision = match_pair(
        complaint(Category.POTHOLE, text="Pothole at Block A Jalan Ampang"),
        complaint(Category.POTHOLE, text="Pothole at Block B Jalan Ampang"),
        0.99,
        POLICY,
    )

    assert decision.decision is MatchState.NO_MATCH
    assert decision.location_compatibility is LocationCompatibility.CONFLICTING
    assert decision.auto_match is False


def test_missing_explicit_location_requires_review_not_auto_match():
    decision = match_pair(
        complaint(Category.POTHOLE, text="Pothole near school"),
        complaint(Category.POTHOLE, text="Pothole near school"),
        0.99,
        POLICY,
    )

    assert decision.decision is MatchState.REVIEW_REQUIRED
    assert decision.location_compatibility is LocationCompatibility.UNKNOWN
    assert decision.review_required is True
