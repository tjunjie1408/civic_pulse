import math
from collections.abc import Sequence

import pytest
from pytest import MonkeyPatch

from civicpulse.embeddings import (
    ModelCacheInvalid,
    ModelCacheUnavailable,
    SentenceTransformerProvider,
    cosine_similarity,
)


class CountingModel:
    def __init__(self, vectors: dict[str, Sequence[float]]) -> None:
        self.vectors = vectors
        self.calls = 0

    def encode(
        self,
        inputs: list[str],
        *,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> list[Sequence[float]]:
        self.calls += 1
        assert normalize_embeddings is True
        assert show_progress_bar is False
        return [self.vectors[text] for text in inputs]


def test_provider_caches_repeated_texts_by_model_and_normalization_version() -> None:
    model = CountingModel({"one": [1.0, 0.0], "two": [0.0, 1.0]})
    provider = SentenceTransformerProvider(
        "fake-model",
        "normalization-v1",
        model_factory=lambda: model,
    )

    first = provider.embed(["one", "two"])
    second = provider.embed(["two", "one"])

    assert first == ((1.0, 0.0), (0.0, 1.0))
    assert second == ((0.0, 1.0), (1.0, 0.0))
    assert model.calls == 1


def test_provider_rejects_non_finite_embeddings() -> None:
    model = CountingModel({"bad": [math.nan, 0.0]})
    provider = SentenceTransformerProvider(
        "fake-model", "normalization-v1", model_factory=lambda: model
    )

    with pytest.raises(ValueError, match="finite"):
        provider.embed(["bad"])


def test_cosine_similarity_validates_dimensions_and_returns_expected_value() -> None:
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    assert cosine_similarity((1.0, 1.0), (1.0, 1.0)) == pytest.approx(1.0)

    with pytest.raises(ValueError, match="dimension"):
        cosine_similarity((1.0,), (1.0, 0.0))


def test_runtime_factory_forces_local_only(monkeypatch: MonkeyPatch) -> None:
    observed: dict[str, bool] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: bool) -> None:
            observed.update(kwargs)

        def encode(
            self,
            inputs: list[str],
            *,
            normalize_embeddings: bool,
            show_progress_bar: bool,
        ) -> list[list[float]]:
            return [[1.0, 0.0, 0.0, 0.0] for _ in inputs]

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", FakeSentenceTransformer)
    provider = SentenceTransformerProvider.for_runtime(
        "cached-model", "normalization-v1", expected_dimension=4
    )
    provider.embed(["probe"])

    assert observed["local_files_only"] is True


def test_missing_cache_error_is_stable_and_sanitized(monkeypatch: MonkeyPatch) -> None:
    class MissingModel:
        def __init__(self, model_name: str, **kwargs: bool) -> None:
            raise OSError("C:/private/cache/secret-model/config.json missing")

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", MissingModel)
    provider = SentenceTransformerProvider.for_runtime("cached-model", "normalization-v1")

    with pytest.raises(ModelCacheUnavailable) as caught:
        provider.embed(["probe"])

    assert caught.value.code == "embedding_model_cache_missing"
    assert "C:/private" not in str(caught.value)
    assert "prewarm_model" in str(caught.value)


def test_expected_dimension_rejects_invalid_model() -> None:
    model = CountingModel({"probe": [1.0, 0.0]})
    provider = SentenceTransformerProvider.for_runtime(
        "cached-model",
        "normalization-v1",
        expected_dimension=384,
        model_factory=lambda: model,
    )

    with pytest.raises(ModelCacheInvalid, match="embedding_model_cache_invalid"):
        provider.embed(["probe"])


def test_prewarm_and_benchmark_keep_explicit_download_modes(monkeypatch: MonkeyPatch) -> None:
    observed: list[bool] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: bool) -> None:
            observed.append(kwargs["local_files_only"])

        def encode(
            self,
            inputs: list[str],
            *,
            normalize_embeddings: bool,
            show_progress_bar: bool,
        ) -> list[list[float]]:
            return [[1.0, 0.0] for _ in inputs]

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", FakeSentenceTransformer)
    SentenceTransformerProvider.for_prewarm("model", "normalization-v1").embed(["a"])
    SentenceTransformerProvider.for_prewarm(
        "model", "normalization-v1", offline=True
    ).embed(["b"])
    SentenceTransformerProvider.for_benchmark("model", "normalization-v1").embed(["c"])

    assert observed == [False, True, False]
