from datetime import UTC, datetime

import pytest
from pytest import MonkeyPatch

from civicpulse.config import load_matching_policy
from civicpulse.domain import Category
from civicpulse.embeddings import ModelCacheUnavailable
from scripts import prewarm_model, run_embedding_benchmark, run_hybrid_benchmark
from scripts.run_embedding_benchmark import BenchmarkPair


class FakeProvider:
    model_name = "fake-model"
    normalization_version = "normalization-v1"

    def embed(self, texts: list[str]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, *([0.0] * 383)) for _ in texts)


def _pair() -> BenchmarkPair:
    reported_at = datetime(2026, 7, 10, 8, tzinfo=UTC)
    return BenchmarkPair(
        id="mode-pair",
        group="mode",
        semantic_expected="match",
        incident_expected="match",
        positive_type="clear",
        complaint_a="Pothole near the school",
        complaint_b="Large pothole by the school",
        rationale="same synthetic location",
        category_a=Category.POTHOLE,
        category_b=Category.POTHOLE,
        latitude_a=3.1,
        longitude_a=101.6,
        latitude_b=3.1001,
        longitude_b=101.6001,
        reported_at_a=reported_at,
        reported_at_b=reported_at,
        split="calibration",
    )


def test_prewarm_offline_selects_local_only(monkeypatch: MonkeyPatch) -> None:
    observed: list[bool] = []

    def factory(*args: object, **kwargs: object) -> FakeProvider:
        observed.append(bool(kwargs["offline"]))
        return FakeProvider()

    monkeypatch.setattr(
        prewarm_model.SentenceTransformerProvider,
        "for_prewarm",
        factory,
    )

    assert prewarm_model.prewarm(offline=True) == 0
    assert observed == [True]


def test_prewarm_default_allows_download(monkeypatch: MonkeyPatch) -> None:
    observed: list[bool] = []

    def factory(*args: object, **kwargs: object) -> FakeProvider:
        observed.append(bool(kwargs["offline"]))
        return FakeProvider()

    monkeypatch.setattr(
        prewarm_model.SentenceTransformerProvider,
        "for_prewarm",
        factory,
    )

    assert prewarm_model.prewarm() == 0
    assert observed == [False]


def test_offline_prewarm_missing_cache_fails_without_download(
    monkeypatch: MonkeyPatch,
) -> None:
    observed: list[bool] = []

    def unavailable(*args: object, **kwargs: object) -> FakeProvider:
        observed.append(bool(kwargs["offline"]))
        raise ModelCacheUnavailable

    monkeypatch.setattr(
        prewarm_model.SentenceTransformerProvider,
        "for_prewarm",
        unavailable,
    )

    with pytest.raises(ModelCacheUnavailable) as caught:
        prewarm_model.prewarm(offline=True)

    assert caught.value.code == "embedding_model_cache_missing"
    assert "C:/" not in str(caught.value)
    assert observed == [True]


def test_hybrid_benchmark_uses_benchmark_factory(monkeypatch: MonkeyPatch) -> None:
    observed: list[bool] = []

    def factory(*args: object, **kwargs: object) -> FakeProvider:
        observed.append(True)
        return FakeProvider()

    monkeypatch.setattr(
        run_hybrid_benchmark.SentenceTransformerProvider,
        "for_benchmark",
        factory,
    )
    policy = load_matching_policy("config/matching_policy.json")

    run_hybrid_benchmark.run_real_benchmark([_pair()], policy)

    assert observed == [True]


def test_embedding_benchmark_uses_benchmark_factory(monkeypatch: MonkeyPatch) -> None:
    observed: list[bool] = []

    def factory(*args: object, **kwargs: object) -> FakeProvider:
        observed.append(True)
        return FakeProvider()

    monkeypatch.setattr(
        run_embedding_benchmark.SentenceTransformerProvider,
        "for_benchmark",
        factory,
    )

    run_embedding_benchmark.score_pairs([_pair()], "fake-model")

    assert observed == [True]
