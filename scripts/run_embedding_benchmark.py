"""Measure whether a multilingual embedding model separates complaint pairs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Literal, TypedDict, cast

from pydantic import BaseModel, ConfigDict, Field

from civicpulse.domain import Category
from civicpulse.embeddings import SentenceTransformerProvider, cosine_similarity


DEFAULT_DATA_PATH = Path("benchmarks/manglish_complaint_pairs.json")
DEFAULT_MODEL = "intfloat/multilingual-e5-small"


class TextPairRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    group: str = Field(min_length=1)
    expected: Literal["match", "non_match"]
    positive_type: Literal["clear", "ambiguous"] | None = None
    incident_expected: Literal["match", "non_match"] | None = None
    complaint_a: str = Field(min_length=1)
    complaint_b: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class IncidentPairMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    category_a: Category
    category_b: Category
    latitude_a: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude_a: float = Field(ge=-180, le=180, allow_inf_nan=False)
    latitude_b: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude_b: float = Field(ge=-180, le=180, allow_inf_nan=False)
    reported_at_a: datetime
    reported_at_b: datetime
    split: Literal["calibration", "holdout"]
    incident_expected: Literal["match", "non_match"]


class BenchmarkPair(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    group: str = Field(min_length=1)
    semantic_expected: Literal["match", "non_match"]
    incident_expected: Literal["match", "non_match"]
    positive_type: Literal["clear", "ambiguous"] | None = None
    complaint_a: str = Field(min_length=1)
    complaint_b: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    category_a: Category
    category_b: Category
    latitude_a: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude_a: float = Field(ge=-180, le=180, allow_inf_nan=False)
    latitude_b: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude_b: float = Field(ge=-180, le=180, allow_inf_nan=False)
    reported_at_a: datetime
    reported_at_b: datetime
    split: Literal["calibration", "holdout"]


class ScoredBenchmarkPair(BenchmarkPair):
    similarity: float = Field(ge=-1, le=1, allow_inf_nan=False)


class ThresholdResult(TypedDict):
    threshold: float
    false_merges: int
    false_splits: int
    precision: float
    recall: float
    f1: float


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read benchmark JSON {path}: {exc}") from exc


def _load_json_list(path: Path) -> list[object]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Benchmark file {path} must contain a JSON array.")
    # JSON decoding is an external boundary; Pydantic validates each element immediately after this cast.
    return cast(list[object], payload)


def load_pairs(path: str | Path) -> list[BenchmarkPair]:
    """Load text pairs and join their typed incident metadata sidecar."""
    text_path = Path(path)
    metadata_path = text_path.with_name("incident_pair_metadata.json")
    text_records: list[TextPairRecord] = [
        TextPairRecord.model_validate(item) for item in _load_json_list(text_path)
    ]
    metadata_records: list[IncidentPairMetadata] = [
        IncidentPairMetadata.model_validate(item)
        for item in _load_json_list(metadata_path)
    ]
    text_by_id = {record.id: record for record in text_records}
    metadata_by_id = {record.id: record for record in metadata_records}
    if set(text_by_id) != set(metadata_by_id):
        raise ValueError("Benchmark text and metadata IDs must match exactly.")
    for record in text_records:
        metadata = metadata_by_id[record.id]
        if record.incident_expected is not None and record.incident_expected != metadata.incident_expected:
            raise ValueError(f"Benchmark incident label mismatch for {record.id}.")

    return [
        BenchmarkPair(
            id=record.id,
            group=record.group,
            semantic_expected=record.expected,
            positive_type=record.positive_type,
            incident_expected=metadata.incident_expected,
            complaint_a=record.complaint_a,
            complaint_b=record.complaint_b,
            rationale=record.rationale,
            category_a=metadata.category_a,
            category_b=metadata.category_b,
            latitude_a=metadata.latitude_a,
            longitude_a=metadata.longitude_a,
            latitude_b=metadata.latitude_b,
            longitude_b=metadata.longitude_b,
            reported_at_a=metadata.reported_at_a,
            reported_at_b=metadata.reported_at_b,
            split=metadata.split,
        )
        for record in text_records
        for metadata in [metadata_by_id[record.id]]
    ]


def find_best_threshold(labeled_scores: list[tuple[float, Literal["match", "non_match"]]]) -> ThresholdResult:
    """Choose a conservative threshold, treating false merges as the main risk."""
    if not labeled_scores:
        raise ValueError("At least one labelled similarity score is required.")

    unique_scores = sorted({score for score, _ in labeled_scores})
    candidates = unique_scores + [
        (lower + upper) / 2
        for lower, upper in zip(unique_scores, unique_scores[1:])
    ]
    results: list[ThresholdResult] = []
    for threshold in candidates:
        true_positives = sum(
            score >= threshold and label == "match" for score, label in labeled_scores
        )
        false_positives = sum(
            score >= threshold and label == "non_match" for score, label in labeled_scores
        )
        false_negatives = sum(
            score < threshold and label == "match" for score, label in labeled_scores
        )
        precision = true_positives / (true_positives + false_positives) if true_positives + false_positives else 0.0
        recall = true_positives / (true_positives + false_negatives) if true_positives + false_negatives else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        results.append({
            "threshold": threshold,
            "false_merges": false_positives,
            "false_splits": false_negatives,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        })

    return max(
        results,
        key=lambda result: (
            -result["false_merges"],
            result["f1"],
            result["precision"],
            result["threshold"],
        ),
    )


def score_pairs(pairs: list[BenchmarkPair], model_name: str) -> list[ScoredBenchmarkPair]:
    """Embed both sides of every pair and attach cosine similarities."""
    provider = SentenceTransformerProvider(model_name, normalization_version="raw-v1")
    texts = [
        prefixed
        for pair in pairs
        for prefixed in (f"query: {pair.complaint_a}", f"passage: {pair.complaint_b}")
    ]
    embeddings = provider.embed(texts)
    return [
        ScoredBenchmarkPair(
            **pair.model_dump(),
            similarity=cosine_similarity(embeddings[index * 2], embeddings[index * 2 + 1]),
        )
        for index, pair in enumerate(pairs)
    ]


def print_report(scored_pairs: list[ScoredBenchmarkPair]) -> None:
    """Print semantic distributions and the cases requiring inspection."""
    positive_scores = [pair.similarity for pair in scored_pairs if pair.semantic_expected == "match"]
    negative_scores = [pair.similarity for pair in scored_pairs if pair.semantic_expected == "non_match"]
    recommendation = find_best_threshold(
        [(pair.similarity, pair.semantic_expected) for pair in scored_pairs]
    )
    print(f"Semantic pairs: {len(scored_pairs)} ({len(positive_scores)} match, {len(negative_scores)} non-match)")
    print(f"Match similarity: min={min(positive_scores):.3f}, mean={mean(positive_scores):.3f}, max={max(positive_scores):.3f}")
    print(f"Non-match similarity: min={min(negative_scores):.3f}, mean={mean(negative_scores):.3f}, max={max(negative_scores):.3f}")
    print(f"Recommended conservative semantic threshold: {recommendation['threshold']:.3f} (false merges={recommendation['false_merges']}, false splits={recommendation['false_splits']}, F1={recommendation['f1']:.3f})")
    print("\nClosest non-matches to inspect (risk of false merge):")
    for pair in sorted(
        (pair for pair in scored_pairs if pair.semantic_expected == "non_match"),
        key=lambda pair: pair.similarity,
        reverse=True,
    )[:5]:
        print(f"- {pair.id} {pair.similarity:.3f}: {pair.rationale}")
    print("\nWeakest matches to inspect (risk of false split):")
    for pair in sorted(
        (pair for pair in scored_pairs if pair.semantic_expected == "match"),
        key=lambda pair: pair.similarity,
    )[:5]:
        print(f"- {pair.id} {pair.similarity:.3f}: {pair.rationale}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    print(f"Model: {args.model}")
    print("This benchmark evaluates semantic similarity only; geo and time constraints remain separate.")
    print_report(score_pairs(load_pairs(args.data), args.model))


if __name__ == "__main__":
    main()
