"""Typed local embedding provider with deterministic in-memory caching."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from hashlib import sha256
from math import isfinite, sqrt
from typing import Protocol, cast

Vector = tuple[float, ...]
EmbeddingMatrix = tuple[Vector, ...]


class ModelCacheUnavailable(RuntimeError):
    """The configured model cannot be loaded from the permitted local cache."""

    code = "embedding_model_cache_missing"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "The configured embedding model is not available in the local cache. "
            "Run: uv run python -m scripts.prewarm_model"
        )


class ModelCacheInvalid(ValueError):
    """The loaded model produced vectors that violate the configured contract."""

    code = "embedding_model_cache_invalid"

    def __init__(self, message: str = "embedding_model_cache_invalid") -> None:
        super().__init__(message)


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
    value = sum(left * right for left, right in zip(first, second, strict=True)) / (
        first_norm * second_norm
    )
    return max(-1.0, min(1.0, value))


class SentenceTransformerProvider:
    """Load a SentenceTransformer lazily and cache normalized text vectors."""

    def __init__(
        self,
        model_name: str,
        normalization_version: str,
        *,
        local_files_only: bool = False,
        expected_dimension: int | None = None,
        model_factory: Callable[[], SentenceEncoder] | None = None,
    ) -> None:
        self.model_name = model_name
        self.normalization_version = normalization_version
        self.local_files_only = local_files_only
        self.expected_dimension = expected_dimension
        self._model_factory = model_factory
        self._model: SentenceEncoder | None = None
        self._cache: dict[str, Vector] = {}
        self._dimension: int | None = None

    @classmethod
    def for_runtime(
        cls,
        model_name: str,
        normalization_version: str,
        *,
        expected_dimension: int | None = None,
        model_factory: Callable[[], SentenceEncoder] | None = None,
    ) -> SentenceTransformerProvider:
        return cls(
            model_name,
            normalization_version,
            local_files_only=True,
            expected_dimension=expected_dimension,
            model_factory=model_factory,
        )

    @classmethod
    def for_prewarm(
        cls,
        model_name: str,
        normalization_version: str,
        *,
        offline: bool = False,
        expected_dimension: int | None = None,
        model_factory: Callable[[], SentenceEncoder] | None = None,
    ) -> SentenceTransformerProvider:
        return cls(
            model_name,
            normalization_version,
            local_files_only=offline,
            expected_dimension=expected_dimension,
            model_factory=model_factory,
        )

    @classmethod
    def for_benchmark(
        cls,
        model_name: str,
        normalization_version: str,
        *,
        expected_dimension: int | None = None,
        model_factory: Callable[[], SentenceEncoder] | None = None,
    ) -> SentenceTransformerProvider:
        return cls(
            model_name,
            normalization_version,
            local_files_only=False,
            expected_dimension=expected_dimension,
            model_factory=model_factory,
        )

    def _get_model(self) -> SentenceEncoder:
        if self._model is None:
            try:
                if self._model_factory is not None:
                    self._model = self._model_factory()
                else:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:
                        raise RuntimeError(
                            "sentence-transformers is unavailable; run `uv sync --frozen`."
                        ) from exc
                    self._model = cast(
                        SentenceEncoder,
                        SentenceTransformer(
                            self.model_name,
                            local_files_only=self.local_files_only,
                        ),
                    )
            except (OSError, RuntimeError, ValueError) as exc:
                if self.local_files_only:
                    raise ModelCacheUnavailable from exc
                raise
        return self._model

    def _cache_key(self, text: str) -> str:
        identity = f"{self.model_name}\0{self.normalization_version}\0{text}".encode()
        return sha256(identity).hexdigest()

    def embed(self, texts: Sequence[str]) -> EmbeddingMatrix:
        unique_missing = list(
            dict.fromkeys(text for text in texts if self._cache_key(text) not in self._cache)
        )
        if unique_missing:
            raw = self._get_model().encode(
                unique_missing,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            rows = cast(Sequence[Sequence[object]], raw)
            if len(rows) != len(unique_missing):
                raise ModelCacheInvalid("embedding_model_cache_invalid: unexpected row count")
            for text, row in zip(unique_missing, rows, strict=True):
                # The model SDK exposes numeric rows without a stable static type; validate here.
                try:
                    vector = tuple(float(cast(float, value)) for value in row)
                except (TypeError, ValueError) as exc:
                    raise ModelCacheInvalid(
                        "embedding_model_cache_invalid: non-numeric vector"
                    ) from exc
                if not vector or not all(isfinite(value) for value in vector):
                    raise ModelCacheInvalid(
                        "embedding_model_cache_invalid: empty or non-finite vector"
                    )
                if self._dimension is None:
                    self._dimension = len(vector)
                if len(vector) != self._dimension:
                    raise ModelCacheInvalid(
                        "embedding_model_cache_invalid: inconsistent vector dimension"
                    )
                if self.expected_dimension is not None and len(vector) != self.expected_dimension:
                    raise ModelCacheInvalid(
                        "embedding_model_cache_invalid: expected dimension "
                        f"{self.expected_dimension}"
                    )
                self._cache[self._cache_key(text)] = vector
        return tuple(self._cache[self._cache_key(text)] for text in texts)
