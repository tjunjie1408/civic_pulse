from __future__ import annotations

import json
from pathlib import Path

import pytest

from civicpulse.performance import (
    MeasurementEnvironment,
    MetricSummary,
    PerformanceBudget,
    PerformanceReport,
    evaluate_budget,
    summarize,
)


def test_p95_uses_deterministic_nearest_rank() -> None:
    summary = summarize([10.0, 20.0, 30.0, 40.0])

    assert summary.count == 4
    assert summary.p50 == 20.0
    assert summary.p95 == 40.0
    assert summary.maximum == 40.0


def test_budget_loads_run_counts_and_thresholds() -> None:
    budget = PerformanceBudget.load(Path("config/performance_budget.json"))

    assert budget.budget_version == "prototype-1"
    assert budget.warmup_runs == 3
    assert budget.measured_runs == 20
    assert budget.startup_runs == 5
    assert budget.reset_runs == 5
    assert budget.dashboard_runs == 5
    assert budget.submission_p95_ms_max == 2500.0
    assert budget.review_resolution_p95_ms_max == 2000.0


def test_hard_breach_fails_but_informational_breach_does_not() -> None:
    budget = PerformanceBudget.load(Path("config/performance_budget.json"))
    evaluation = evaluate_budget(
        budget,
        {
            "incident_list_p95_ms": MetricSummary(count=3, p50=200.0, p95=300.0, maximum=300.0),
            "cold_start_ms": MetricSummary(count=3, p50=9000.0, p95=9000.0, maximum=9000.0),
        },
        rss_growth_percent=0.0,
    )

    assert evaluation.passed is False
    assert evaluation.metrics["incident_list_p95_ms"].hard is True
    assert evaluation.metrics["cold_start_ms"].hard is False
    assert evaluation.metrics["cold_start_ms"].passed is True


def test_submission_and_review_gate_use_slowest_scenario() -> None:
    budget = PerformanceBudget.load(Path("config/performance_budget.json"))
    evaluation = evaluate_budget(
        budget,
        {
            "submission_isolated_p95_ms": MetricSummary(
                count=20, p50=100.0, p95=100.0, maximum=100.0
            ),
            "submission_auto_match_p95_ms": MetricSummary(
                count=20, p50=200.0, p95=200.0, maximum=200.0
            ),
            "submission_review_required_p95_ms": MetricSummary(
                count=20, p50=3000.0, p95=3000.0, maximum=3000.0
            ),
            "review_approve_p95_ms": MetricSummary(count=20, p50=100.0, p95=100.0, maximum=100.0),
            "review_reject_p95_ms": MetricSummary(count=20, p50=200.0, p95=200.0, maximum=200.0),
            "review_merge_p95_ms": MetricSummary(count=20, p50=2500.0, p95=2500.0, maximum=2500.0),
        },
        rss_growth_percent=0.0,
    )

    assert evaluation.metrics["submission_p95_ms"].observed == 3000.0
    assert evaluation.metrics["submission_p95_ms"].passed is False
    assert evaluation.metrics["review_resolution_p95_ms"].observed == 2500.0
    assert evaluation.metrics["review_resolution_p95_ms"].passed is False


def test_report_round_trip_rejects_unknown_fields() -> None:
    budget = PerformanceBudget.load(Path("config/performance_budget.json"))
    report = PerformanceReport(
        environment=MeasurementEnvironment(
            os="test",
            cpu="test",
            ram_mb=1024.0,
            python_version="3.12",
            model_name="cached-model",
            seed_size=120,
            database_backend="SQLite local file",
            offline_mode=True,
            warmup_runs=3,
            measured_runs=20,
            measurement_method="perf_counter",
        ),
        budget_version=budget.budget_version,
        timestamp="2026-07-14T00:00:00Z",
        git_commit="abc123",
        git_dirty=False,
        raw_samples={"incident_list_p95_ms": [10.0, 20.0]},
        summaries={"incident_list_p95_ms": summarize([10.0, 20.0])},
        rss={"ready_rss_mb": 100.0},
        evaluations={},
        known_noise_sources=("test",),
        measurement_status="completed",
        hard_gate_passed=True,
    )
    restored = PerformanceReport.model_validate_json(report.model_dump_json())

    assert restored.environment.offline_mode is True
    with pytest.raises(ValueError):
        PerformanceReport.model_validate(
            json.loads(report.model_dump_json()) | {"unexpected": True}
        )
