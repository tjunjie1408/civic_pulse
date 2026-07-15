"""Typed performance-budget contracts and deterministic metric evaluation."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PerformanceBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    budget_version: str = Field(min_length=1)
    warmup_runs: int = Field(ge=1)
    measured_runs: int = Field(ge=1)
    startup_runs: int = Field(ge=1)
    reset_runs: int = Field(ge=1)
    dashboard_runs: int = Field(ge=1)
    cached_readiness_seconds_max: float = Field(gt=0)
    incident_list_p95_ms_max: float = Field(gt=0)
    incident_detail_p95_ms_max: float = Field(gt=0)
    submission_p95_ms_max: float = Field(gt=0)
    review_resolution_p95_ms_max: float = Field(gt=0)
    reset_seconds_max: float = Field(gt=0)
    ready_rss_mb_max: float = Field(gt=0)
    mutation_memory_growth_percent_max: float = Field(gt=0)
    dashboard_first_usable_seconds_max: float = Field(gt=0)

    @classmethod
    def load(cls, path: str | Path) -> PerformanceBudget:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class MeasurementEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    os: str = Field(min_length=1)
    cpu: str = Field(min_length=1)
    ram_mb: float = Field(gt=0)
    python_version: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    seed_size: int = Field(ge=0)
    database_backend: str = Field(min_length=1)
    offline_mode: bool
    warmup_runs: int = Field(ge=0)
    measured_runs: int = Field(ge=0)
    measurement_method: str = Field(min_length=1)


class MetricSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = Field(ge=1)
    p50: float = Field(ge=0)
    p95: float = Field(ge=0)
    maximum: float = Field(ge=0)


class MetricEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observed: float = Field(ge=0)
    limit: float | None = Field(default=None, gt=0)
    hard: bool
    passed: bool


class BudgetEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metrics: dict[str, MetricEvaluation]
    passed: bool


class PerformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: MeasurementEnvironment
    budget_version: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    git_commit: str = Field(min_length=1)
    git_dirty: bool
    raw_samples: dict[str, list[float]]
    summaries: dict[str, MetricSummary]
    rss: dict[str, float]
    evaluations: dict[str, MetricEvaluation]
    known_noise_sources: tuple[str, ...]
    measurement_status: Literal["completed", "incomplete"]
    hard_gate_passed: bool | None


def summarize(samples: Sequence[float]) -> MetricSummary:
    """Summarize non-negative samples using deterministic nearest-rank percentiles."""
    if not samples:
        raise ValueError("At least one performance sample is required.")
    ordered = sorted(float(sample) for sample in samples)
    if any(not math.isfinite(sample) or sample < 0 for sample in ordered):
        raise ValueError("Performance samples must be finite and non-negative.")

    def nearest_rank(percentile: float) -> float:
        rank = max(1, math.ceil(percentile * len(ordered)))
        return ordered[rank - 1]

    return MetricSummary(
        count=len(ordered),
        p50=nearest_rank(0.50),
        p95=nearest_rank(0.95),
        maximum=ordered[-1],
    )


def _evaluation(observed: float, limit: float | None, *, hard: bool) -> MetricEvaluation:
    return MetricEvaluation(
        observed=observed,
        limit=limit,
        hard=hard,
        passed=limit is None or observed <= limit,
    )


def evaluate_budget(
    budget: PerformanceBudget,
    summaries: dict[str, MetricSummary],
    *,
    rss_growth_percent: float,
) -> BudgetEvaluation:
    """Evaluate available metrics and aggregate scenario-specific mutation gates."""
    threshold_by_metric: dict[str, tuple[float, bool]] = {
        "cached_process_readiness_seconds": (budget.cached_readiness_seconds_max, True),
        "incident_list_p95_ms": (budget.incident_list_p95_ms_max, True),
        "incident_detail_p95_ms": (budget.incident_detail_p95_ms_max, True),
        "reset_seconds": (budget.reset_seconds_max, True),
        "ready_rss_mb": (budget.ready_rss_mb_max, True),
        "dashboard_first_usable_seconds": (budget.dashboard_first_usable_seconds_max, True),
        "cold_start_ms": (0.0, False),
    }
    metrics: dict[str, MetricEvaluation] = {}
    for name, summary in summaries.items():
        threshold = threshold_by_metric.get(name)
        if threshold is None or name == "cold_start_ms":
            metrics[name] = _evaluation(summary.p95, None, hard=False)
        else:
            metrics[name] = _evaluation(summary.p95, threshold[0], hard=threshold[1])

    submission_parts = (
        "submission_isolated_p95_ms",
        "submission_auto_match_p95_ms",
        "submission_review_required_p95_ms",
    )
    if all(name in summaries for name in submission_parts):
        observed = max(summaries[name].p95 for name in submission_parts)
        metrics["submission_p95_ms"] = _evaluation(
            observed, budget.submission_p95_ms_max, hard=True
        )

    review_parts = ("review_approve_p95_ms", "review_reject_p95_ms", "review_merge_p95_ms")
    if all(name in summaries for name in review_parts):
        observed = max(summaries[name].p95 for name in review_parts)
        metrics["review_resolution_p95_ms"] = _evaluation(
            observed, budget.review_resolution_p95_ms_max, hard=True
        )

    metrics["mutation_memory_growth_percent"] = _evaluation(
        rss_growth_percent,
        budget.mutation_memory_growth_percent_max,
        hard=True,
    )
    return BudgetEvaluation(
        metrics=metrics,
        passed=all(item.passed for item in metrics.values() if item.hard),
    )


def load_budget(path: str | Path) -> PerformanceBudget:
    """Load a strict budget from a JSON path."""
    resolved = Path(path)
    return PerformanceBudget.model_validate(json.loads(resolved.read_text(encoding="utf-8")))
