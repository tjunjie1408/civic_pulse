"""Conservative complaint-pair matching with explicit location tri-state."""

from __future__ import annotations

from math import isfinite
from typing import TypedDict, Unpack

from civicpulse.config import MatchingPolicy
from civicpulse.domain import (
    Category,
    Complaint,
    LocationCompatibility,
    LocationEntity,
    MatchDecision,
    MatchState,
)
from civicpulse.geo import haversine_metres, temporal_gap_seconds
from civicpulse.location import compare_location_entities, extract_location_entities


class _DecisionContext(TypedDict):
    location_compatibility: LocationCompatibility
    first_location_entities: tuple[LocationEntity, ...]
    second_location_entities: tuple[LocationEntity, ...]
    distance_metres: float
    time_gap_seconds: float
    semantic_similarity: float


def _decision(
    *,
    state: MatchState,
    category_compatible: bool,
    reasons: list[str],
    **context: Unpack[_DecisionContext],
) -> MatchDecision:
    return MatchDecision(
        decision=state,
        auto_match=state is MatchState.AUTO_MATCH,
        review_required=state is MatchState.REVIEW_REQUIRED,
        category_compatible=category_compatible,
        **context,
        reasons=tuple([*reasons, f"final decision: {state.value}"]),
    )


def match_pair(
    first: Complaint,
    second: Complaint,
    semantic_similarity: float,
    policy: MatchingPolicy,
) -> MatchDecision:
    """Use embeddings for candidate compatibility, not as sole identity evidence."""
    if not isfinite(semantic_similarity) or not -1 <= semantic_similarity <= 1:
        raise ValueError("semantic similarity must be finite and between -1 and 1")

    distance_metres = haversine_metres(
        first.latitude,
        first.longitude,
        second.latitude,
        second.longitude,
    )
    time_gap_seconds = temporal_gap_seconds(first.reported_at, second.reported_at)
    first_category = first.category or Category.OTHER
    second_category = second.category or Category.OTHER
    first_entities = extract_location_entities(first.normalized_text)
    second_entities = extract_location_entities(second.normalized_text)
    location = compare_location_entities(first_entities, second_entities)
    common: _DecisionContext = {
        "location_compatibility": location.compatibility,
        "first_location_entities": first_entities,
        "second_location_entities": second_entities,
        "distance_metres": distance_metres,
        "time_gap_seconds": time_gap_seconds,
        "semantic_similarity": semantic_similarity,
    }

    if first_category is Category.OTHER or second_category is Category.OTHER:
        return _decision(
            state=MatchState.REVIEW_REQUIRED,
            category_compatible=False,
            reasons=["category requires officer review", *location.reasons],
            **common,
        )

    if first_category is not second_category:
        return _decision(
            state=MatchState.NO_MATCH,
            category_compatible=False,
            reasons=[f"category mismatch: {first_category} vs {second_category}", *location.reasons],
            **common,
        )

    if distance_metres > policy.geographic_radius_metres:
        return _decision(
            state=MatchState.NO_MATCH,
            category_compatible=True,
            reasons=[
                f"distance {distance_metres:.1f}m exceeds {policy.geographic_radius_metres:.1f}m policy radius",
                *location.reasons,
            ],
            **common,
        )

    if time_gap_seconds > policy.temporal_window_days * 24 * 60 * 60:
        return _decision(
            state=MatchState.NO_MATCH,
            category_compatible=True,
            reasons=[
                f"time gap {time_gap_seconds / 3600:.1f}h exceeds {policy.temporal_window_days:.1f} day policy window",
                *location.reasons,
            ],
            **common,
        )

    if location.compatibility is LocationCompatibility.CONFLICTING:
        return _decision(
            state=MatchState.NO_MATCH,
            category_compatible=True,
            reasons=[*location.reasons, "explicit location conflict prevents auto-match"],
            **common,
        )

    semantic_threshold = (
        policy.strong_entity_semantic_threshold
        if location.compatibility is LocationCompatibility.COMPATIBLE
        else policy.semantic_threshold
    )
    if semantic_similarity < semantic_threshold:
        return _decision(
            state=MatchState.REVIEW_REQUIRED,
            category_compatible=True,
            reasons=[
                f"semantic similarity {semantic_similarity:.3f} is below {semantic_threshold:.3f} threshold",
                *location.reasons,
            ],
            **common,
        )

    if location.compatibility is LocationCompatibility.UNKNOWN:
        return _decision(
            state=MatchState.REVIEW_REQUIRED,
            category_compatible=True,
            reasons=[*location.reasons, "missing explicit location evidence prevents auto-match"],
            **common,
        )

    return _decision(
        state=MatchState.AUTO_MATCH,
        category_compatible=True,
        reasons=[
            f"same category: {first_category}",
            f"distance {distance_metres:.1f}m within policy radius",
            f"time gap {time_gap_seconds / 3600:.1f}h within policy window",
            f"semantic similarity {semantic_similarity:.3f} meets threshold",
            *location.reasons,
        ],
        **common,
    )
