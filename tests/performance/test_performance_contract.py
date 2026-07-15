from __future__ import annotations

import pytest

from civicpulse.performance import PerformanceBudget
from scripts.run_performance_budget import (
    build_api_command,
    build_child_environment,
    classify_exit_code,
    measure_isolated_samples,
    metric_run_count,
    render_markdown_summary,
    rss_growth,
)

pytestmark = pytest.mark.performance


def test_metric_run_counts_use_the_budgeted_cost_class() -> None:
    budget = PerformanceBudget.load("config/performance_budget.json")

    assert metric_run_count("incident_list_p95_ms", budget) == 20
    assert metric_run_count("cached_process_readiness_seconds", budget) == 5
    assert metric_run_count("reset_seconds", budget) == 5
    assert metric_run_count("dashboard_first_usable_seconds", budget) == 5


def test_child_environment_forces_offline_without_leaking_parent_value() -> None:
    child = build_child_environment({"HF_HUB_OFFLINE": "0", "CIVICPULSE_DB_PATH": "temp.db"})

    assert child["HF_HUB_OFFLINE"] == "1"
    assert child["CIVICPULSE_DB_PATH"] == "temp.db"


def test_exit_code_distinguishes_gate_failure_from_incomplete_measurement() -> None:
    assert classify_exit_code(measurement_status="completed", hard_gate_passed=True) == 0
    assert classify_exit_code(measurement_status="completed", hard_gate_passed=False) == 1
    assert classify_exit_code(measurement_status="incomplete", hard_gate_passed=None) == 2


def test_api_command_uses_runtime_factory_and_health_endpoint_contract() -> None:
    command = build_api_command(port=8123)

    assert "civicpulse.runtime:create_runtime_app" in command
    assert "--factory" in command
    assert command[-1] == "8123"


def test_mutation_samples_reset_and_warm_before_each_timed_operation() -> None:
    events: list[str] = []
    ticks = iter([1.0, 1.2, 2.0, 2.5])

    samples = measure_isolated_samples(
        reset=lambda: events.append("reset"),
        warm=lambda: events.append("warm"),
        operation=lambda: events.append("operation"),
        runs=2,
        clock=lambda: next(ticks),
    )

    assert samples == pytest.approx([200.0, 500.0])
    assert events == ["reset", "warm", "operation", "reset", "warm", "operation"]


def test_markdown_links_to_json_source_of_truth_without_raw_arrays() -> None:
    markdown = render_markdown_summary(
        budget_version="prototype-1",
        raw_json_path="benchmarks/reports/performance-budget.json",
        hard_gate_passed=True,
    )

    assert "benchmarks/reports/performance-budget.json" in markdown
    assert "Raw samples are retained" in markdown
    assert "[10.0" not in markdown


def test_rss_growth_reports_absolute_and_percentage_values() -> None:
    growth_mb, growth_percent = rss_growth(1000.0, 1100.0)

    assert growth_mb == pytest.approx(100.0)
    assert growth_percent == pytest.approx(10.0)
