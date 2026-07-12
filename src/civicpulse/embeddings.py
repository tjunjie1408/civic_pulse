"""Typed local embedding provider with deterministic in-memory caching."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from hashlib import sha256
from math import isfinite, sqrt
from typing import Protocol, cast


Vector = tuple[float, ...]
EmbeddingMatrix = tuple[Vector, ...]


class SentenceEncoder(Protocol):
    def encode(
        self,
        inputs: list[str],
        *,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> object: ...


class EmbeddingProvider(Protocol):
    model_name: str
    normalization_version: str

    def embed(self, texts: Sequence[str]) -> EmbeddingMatrix: ...


def cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    if len(first) != len(second):
        raise ValueError("embedding vectors must have the same dimension")
    if not first:
        raise ValueError("embedding vectors cannot be empty")
    if not all(isfinite(value) for value in (*first, *second)):
        raise ValueError("embedding vectors must contain only finite values")
    first_norm = sqrt(sum(value * value for value in first))
    second_norm = sqrt(sum(value * value for value in second))
    if first_norm == 0 or second_norm == 0:
        raise ValueError("embedding vectors cannot have zero norm")
    value = sum(left * right for left, right in zip(first, second, strict=True)) / (first_norm * second_norm)
    return max(-1.0, min(1.0, value))


class SentenceTransformerProvider:
    """Load a SentenceTransformer lazily and cache normalized text vectors."""

    def __init__(
        self,
        model_name: str,
        normalization_version: str,
        model_factory: Callable[[], SentenceEncoder] | None = None,
    ) -> None:
        self.model_name = model_name
        self.normalization_version = normalization_version
        self._model_factory = model_factory
        self._model: SentenceEncoder | None = None
        self._cache: dict[str, Vector] = {}
        self._dimension: int | None = None

    def _get_model(self) -> SentenceEncoder:
        if self._model is None:
            if self._model_factory is not None:
                self._model = self._model_factory()
            else:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    raise RuntimeError(
                        "sentence-transformers is unavailable; run `uv sync --frozen`."
                    ) from exc
                self._model = cast(SentenceEncoder, SentenceTransformer(self.model_name))
        return self._model

    def _cache_key(self, text: str) -> str:
        identity = f"{self.model_name}\0{self.normalization_version}\0{text}".encode("utf-8")
        return sha256(identity).hexdigest()

    def embed(self, texts: Sequence[str]) -> EmbeddingMatrix:
        unique_missing = list(dict.fromkeys(text for text in texts if self._cache_key(text) not in self._cache))
        if unique_missing:
            raw = self._get_model().encode(
                unique_missing,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            rows = cast(Sequence[Sequence[object]], raw)
            if len(rows) != len(unique_missing):
                raise ValueError("embedding provider returned an unexpected row count")
            for text, row in zip(unique_missing, rows, strict=True):
                # The model SDK exposes numeric rows without a stable static type; validate by conversion here.
                vector = tuple(float(cast(float, value)) for value in row)
                if not vector or not all(isfinite(value) for value in vector):
                    raise ValueError("embedding provider returned non-finite or empty vectors")
                if self._dimension is None:
                    self._dimension = len(vector)
                if len(vector) != self._dimension:
                    raise ValueError("embedding provider returned inconsistent vector dimension")
                self._cache[self._cache_key(text)] = vector
        return tuple(self._cache[self._cache_key(text)] for text in texts)
