"""Run the calibration/holdout gate for hybrid incident matching."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from civicpulse.config import MatchingPolicy, load_matching_policy
from civicpulse.domain import (
    Category,
    Complaint,
    LocationCompatibility,
    LocationEntity,
    MatchState,
)
from civicpulse.embeddings import SentenceTransformerProvider, cosine_similarity
from civicpulse.matching import match_pair
from civicpulse.normalize import normalize_text
from scripts.run_embedding_benchmark import BenchmarkPair, find_best_threshold, load_pairs


class BenchmarkDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    split: Literal["calibration", "holdout"]
    incident_expected: Literal["match", "non_match"]
    positive_type: Literal["clear", "ambiguous"] | None = None
    semantic_similarity: float = Field(ge=-1, le=1)
    decision: MatchState
    auto_match: bool
    location_compatibility: LocationCompatibility
    first_location_entities: tuple[LocationEntity, ...]
    second_location_entities: tuple[LocationEntity, ...]
    reasons: tuple[str, ...] = Field(min_length=1)


class HybridBenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_version: str
    model_name: str
    normalization_version: str
    calibration_threshold: float
    holdout_false_merges: int = Field(ge=0)
    holdout_true_matches: int = Field(ge=0)
    holdout_false_auto_merges: int = Field(ge=0)
    holdout_auto_matches: int = Field(ge=0)
    holdout_review_required: int = Field(ge=0)
    holdout_no_matches: int = Field(ge=0)
    holdout_positive_no_matches: int = Field(ge=0)
    holdout_clear_positive_count: int = Field(ge=0)
    holdout_clear_auto_matches: int = Field(ge=0)
    holdout_clear_positive_no_matches: int = Field(ge=0)
    clear_positive_auto_rate: float = Field(ge=0, le=1)
    holdout_positive_count: int = Field(ge=0)
    holdout_negative_count: int = Field(ge=0)
    passed: bool
    decisions: tuple[BenchmarkDecision, ...]


def _complaint(
    text: str,
    category: Category,
    latitude: float,
    longitude: float,
    reported_at: datetime,
) -> Complaint:
    return Complaint(
        text=text,
        normalized_text=normalize_text(text),
        category=category,
        latitude=latitude,
        longitude=longitude,
        reported_at=reported_at,
    )


def evaluate_pairs(
    pairs: list[BenchmarkPair],
    similarity_by_id: Mapping[str, float],
    policy: MatchingPolicy,
) -> HybridBenchmarkReport:
    """Evaluate a frozen set without allowing holdout scores into calibration."""
    pair_ids = {pair.id for pair in pairs}
    if set(similarity_by_id) != pair_ids:
        raise ValueError("Similarity IDs must match benchmark IDs exactly.")
    calibration_scores: list[tuple[float, Literal["match", "non_match"]]] = [
        (similarity_by_id[pair.id], pair.semantic_expected)
        for pair in pairs
        if pair.split == "calibration"
    ]
    threshold_result = find_best_threshold(calibration_scores)
    evaluated_policy = policy.model_copy(update={"semantic_threshold": threshold_result["threshold"]})
    decisions: list[BenchmarkDecision] = []
    for pair in pairs:
        latest_time = max(pair.reported_at_a, pair.reported_at_b)
        shift = min(
            timedelta(0),
            datetime.now(timezone.utc) - timedelta(minutes=6) - latest_time.astimezone(timezone.utc),
        )
        first = _complaint(
            pair.complaint_a,
            pair.category_a,
            pair.latitude_a,
            pair.longitude_a,
            pair.reported_at_a + shift,
        )
        second = _complaint(
            pair.complaint_b,
            pair.category_b,
            pair.latitude_b,
            pair.longitude_b,
            pair.reported_at_b + shift,
        )
        decision = match_pair(first, second, similarity_by_id[pair.id], evaluated_policy)
        decisions.append(
            BenchmarkDecision(
                id=pair.id,
                split=pair.split,
                incident_expected=pair.incident_expected,
                positive_type=pair.positive_type,
                semantic_similarity=similarity_by_id[pair.id],
                decision=decision.decision,
                auto_match=decision.auto_match,
                location_compatibility=decision.location_compatibility,
                first_location_entities=decision.first_location_entities,
                second_location_entities=decision.second_location_entities,
                reasons=decision.reasons,
            )
        )

    holdout = [decision for decision in decisions if decision.split == "holdout"]
    holdout_false_auto_merges = sum(
        decision.auto_match and decision.incident_expected == "non_match" for decision in holdout
    )
    holdout_auto_matches = sum(
        decision.auto_match and decision.incident_expected == "match" for decision in holdout
    )
    holdout_review_required = sum(decision.decision is MatchState.REVIEW_REQUIRED for decision in holdout)
    holdout_no_matches = sum(decision.decision is MatchState.NO_MATCH for decision in holdout)
    holdout_positive_no_matches = sum(
        decision.decision is MatchState.NO_MATCH and decision.incident_expected == "match"
        for decision in holdout
    )
    clear_positives = [
        decision
        for decision in holdout
        if decision.incident_expected == "match" and decision.positive_type == "clear"
    ]
    holdout_clear_positive_count = len(clear_positives)
    holdout_clear_auto_matches = sum(
        decision.decision is MatchState.AUTO_MATCH for decision in clear_positives
    )
    holdout_clear_positive_no_matches = sum(
        decision.decision is MatchState.NO_MATCH for decision in clear_positives
    )
    clear_positive_auto_rate = (
        holdout_clear_auto_matches / holdout_clear_positive_count
        if holdout_clear_positive_count
        else 0.0
    )
    holdout_positive_count = sum(decision.incident_expected == "match" for decision in holdout)
    holdout_negative_count = sum(decision.incident_expected == "non_match" for decision in holdout)
    return HybridBenchmarkReport(
        benchmark_version="hybrid-matching-v1",
        model_name=policy.model_name,
        normalization_version=policy.normalization_version,
        calibration_threshold=threshold_result["threshold"],
        holdout_false_merges=holdout_false_auto_merges,
        holdout_true_matches=holdout_auto_matches,
        holdout_false_auto_merges=holdout_false_auto_merges,
        holdout_auto_matches=holdout_auto_matches,
        holdout_review_required=holdout_review_required,
        holdout_no_matches=holdout_no_matches,
        holdout_positive_no_matches=holdout_positive_no_matches,
        holdout_clear_positive_count=holdout_clear_positive_count,
        holdout_clear_auto_matches=holdout_clear_auto_matches,
        holdout_clear_positive_no_matches=holdout_clear_positive_no_matches,
        clear_positive_auto_rate=clear_positive_auto_rate,
        holdout_positive_count=holdout_positive_count,
        holdout_negative_count=holdout_negative_count,
        passed=(
            holdout_false_auto_merges == 0
            and holdout_positive_no_matches == 0
            and holdout_clear_positive_no_matches == 0
            and clear_positive_auto_rate >= 0.75
        ),
        decisions=tuple(decisions),
    )


def run_real_benchmark(pairs: list[BenchmarkPair], policy: MatchingPolicy) -> HybridBenchmarkReport:
    provider = SentenceTransformerProvider(policy.model_name, policy.normalization_version)
    texts = [
        text
        for pair in pairs
        for text in (normalize_text(pair.complaint_a), normalize_text(pair.complaint_b))
    ]
    vectors = provider.embed(texts)
    similarities = {
        pair.id: cosine_similarity(vectors[index * 2], vectors[index * 2 + 1])
        for index, pair in enumerate(pairs)
    }
    return evaluate_pairs(pairs, similarities, policy)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("benchmarks/manglish_complaint_pairs.json"))
    parser.add_argument("--output", type=Path, default=Path("benchmarks/reports/hybrid-matching-v1.json"))
    args = parser.parse_args()
    policy = load_matching_policy("config/matching_policy.json")
    report = run_real_benchmark(load_pairs(args.data), policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(report.model_dump_json(indent=2))
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
