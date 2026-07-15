from __future__ import annotations

import sys

import pytest

import scripts.run_performance_budget as performance_harness
from civicpulse.performance import PerformanceBudget
from scripts.run_performance_budget import (
    build_api_command,
    build_child_environment,
    classify_exit_code,
    dashboard_elapsed_seconds,
    derive_startup_profile_metrics,
    measure_isolated_samples,
    metric_run_count,
    render_markdown_summary,
    rss_growth,
)

pytestmark = pytest.mark.performance


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


class PaginatedReviewClient:
    def __init__(self) -> None:
        self.offsets: list[int] = []

    def get(self, _url: str, *, params: object | None = None) -> FakeResponse:
        assert isinstance(params, dict)
        offset = int(params.get("offset", 0))
        self.offsets.append(offset)
        items = (
            [
                {
                    "left_complaint_id": "seed-a",
                    "right_complaint_id": "seed-b",
                }
            ]
            if offset == 0
            else [
                {
                    "left_complaint_id": "fixture",
                    "right_complaint_id": "measured",
                }
            ]
        )
        return FakeResponse(
            200,
            {"items": items, "limit": 1, "offset": offset, "total": 2},
        )


def test_metric_run_counts_use_the_budgeted_cost_class() -> None:
    budget = PerformanceBudget.load("config/performance_budget.json")

    assert metric_run_count("incident_list_p95_ms", budget) == 20
    assert metric_run_count("cached_process_readiness_seconds", budget) == 5
    assert metric_run_count("application_composition_seconds", budget) == 5
    assert metric_run_count("warm_readiness_seconds", budget) == 5
    assert metric_run_count("cold_cached_model_initialization_seconds", budget) == 5
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
    assert "originally defined cached process readiness as <=8 s" in markdown
    assert "retired as a hard gate, not silently widened" in markdown
    assert "[10.0" not in markdown


def test_rss_growth_reports_absolute_and_percentage_values() -> None:
    growth_mb, growth_percent = rss_growth(1000.0, 1100.0)

    assert growth_mb == pytest.approx(100.0)
    assert growth_percent == pytest.approx(10.0)


def test_dashboard_budget_starts_after_api_readiness() -> None:
    dashboard_seconds, full_demo_seconds = dashboard_elapsed_seconds(
        api_process_started=10.0,
        dashboard_started=21.5,
        dashboard_usable=24.25,
    )

    assert dashboard_seconds == pytest.approx(2.75)
    assert full_demo_seconds == pytest.approx(14.25)


def test_dashboard_timing_rejects_invalid_boundaries() -> None:
    with pytest.raises(ValueError, match="monotonic"):
        dashboard_elapsed_seconds(
            api_process_started=10.0,
            dashboard_started=25.0,
            dashboard_usable=24.0,
        )


def test_startup_profile_separates_application_and_model_cost_centers() -> None:
    application, cold_model = derive_startup_profile_metrics(
        {
            "settings_and_policy_loading": 0.2,
            "database_and_seed_initialization": 2.8,
            "app_composition": 0.1,
            "model_provider_load": 0.3,
            "readiness_probe": 21.7,
        }
    )

    assert application == pytest.approx(3.1)
    assert cold_model == pytest.approx(22.0)


def test_submission_sample_texts_are_deterministic_and_unique() -> None:
    sample_text = getattr(performance_harness, "submission_sample_text", None)
    assert callable(sample_text)

    assert sample_text("isolated", 0) == "isolated performance sample 0"
    assert sample_text("auto_match", 0) == "Road hole at Blok A Jln Ampang pothole sample 0"
    assert sample_text("review_required", 0) == "Pothole near school sample 0"
    assert sample_text("auto_match", 1) != sample_text("auto_match", 0)


def test_timed_result_returns_response_without_timing_later_validation() -> None:
    timed_result = getattr(performance_harness, "timed_milliseconds_with_result", None)
    assert callable(timed_result)
    ticks = iter([1.0, 1.25])

    elapsed, result = timed_result(lambda: "response", clock=lambda: next(ticks))

    assert elapsed == pytest.approx(250.0)
    assert result == "response"


def test_submission_scenario_rejects_wrong_decision_even_after_201() -> None:
    assert_scenario = getattr(performance_harness, "assert_submission_scenario", None)
    assert callable(assert_scenario)
    response = FakeResponse(
        201,
        {
            "complaint": {"complaint_id": "measured"},
            "relationship_decisions": [
                {
                    "left_id": "fixture",
                    "right_id": "measured",
                    "decision": "review_required",
                }
            ],
        },
    )

    with pytest.raises(RuntimeError, match="auto_match"):
        assert_scenario(
            response,
            expected_decision="auto_match",
            fixture_complaint_id="fixture",
        )


def test_submission_scenario_accepts_expected_pair_decision() -> None:
    assert_scenario = getattr(performance_harness, "assert_submission_scenario", None)
    assert callable(assert_scenario)
    response = FakeResponse(
        201,
        {
            "complaint": {"complaint_id": "measured"},
            "relationship_decisions": [
                {
                    "left_id": "fixture",
                    "right_id": "measured",
                    "decision": "auto_match",
                }
            ],
        },
    )

    complaint_id = assert_scenario(
        response,
        expected_decision="auto_match",
        fixture_complaint_id="fixture",
    )

    assert complaint_id == "measured"


def test_isolated_scenario_ignores_unrelated_seed_relationships() -> None:
    response = FakeResponse(
        201,
        {
            "complaint": {"complaint_id": "measured"},
            "relationship_decisions": [
                {"left_id": "seed-a", "right_id": "seed-b", "decision": "auto_match"}
            ],
        },
    )

    complaint_id = performance_harness.assert_submission_scenario(
        response,
        expected_decision="isolated",
    )

    assert complaint_id == "measured"


def test_pending_review_assertion_rejects_missing_pair() -> None:
    assert_pending_pair = getattr(performance_harness, "assert_pending_review_pair", None)
    assert callable(assert_pending_pair)
    response = FakeResponse(200, {"items": [], "limit": 100, "offset": 0, "total": 0})

    with pytest.raises(RuntimeError, match="pending review"):
        assert_pending_pair(response, "fixture", "measured")


def test_pending_review_lookup_paginates_until_pair_is_found() -> None:
    lookup = getattr(performance_harness, "assert_pending_review_pair_via_api", None)
    assert callable(lookup)
    client = PaginatedReviewClient()

    lookup(client, "fixture", "measured", page_size=1)

    assert client.offsets == [0, 1]


def test_main_requires_offline_with_friendly_exit_code_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["run_performance_budget"])

    with pytest.raises(SystemExit) as raised:
        performance_harness.main()

    assert raised.value.code == 2
    assert (
        "Use --offline; the performance harness never downloads models implicitly."
        in capsys.readouterr().err
    )


def test_main_reports_infrastructure_failure_with_exit_code_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_budget(**_kwargs: object) -> None:
        raise RuntimeError("fixture unavailable")

    monkeypatch.setattr(sys, "argv", ["run_performance_budget", "--offline"])
    monkeypatch.setattr(performance_harness, "run_performance_budget", fail_budget)

    with pytest.raises(SystemExit) as raised:
        performance_harness.main()

    assert raised.value.code == 2
    assert (
        "performance measurement infrastructure failed: fixture unavailable"
        in capsys.readouterr().err
    )
