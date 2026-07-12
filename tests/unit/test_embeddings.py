import math

import pytest

from civicpulse.embeddings import SentenceTransformerProvider, cosine_similarity


class CountingModel:
    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = 0

    def encode(self, inputs, *, normalize_embeddings, show_progress_bar):
        self.calls += 1
        assert normalize_embeddings is True
        assert show_progress_bar is False
        return [self.vectors[text] for text in inputs]


def test_provider_caches_repeated_texts_by_model_and_normalization_version():
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


def test_provider_rejects_non_finite_embeddings():
    model = CountingModel({"bad": [math.nan, 0.0]})
    provider = SentenceTransformerProvider("fake-model", "normalization-v1", model_factory=lambda: model)

    with pytest.raises(ValueError, match="finite"):
        provider.embed(["bad"])


def test_cosine_similarity_validates_dimensions_and_returns_expected_value():
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    assert cosine_similarity((1.0, 1.0), (1.0, 1.0)) == pytest.approx(1.0)

    with pytest.raises(ValueError, match="dimension"):
        cosine_similarity((1.0,), (1.0, 0.0))
