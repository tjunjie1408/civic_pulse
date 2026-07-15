from pathlib import Path


def test_offline_recovery_boundaries_are_documented() -> None:
    root = Path(__file__).parents[2]
    text = (root / "README.md").read_text(encoding="utf-8") + (
        root / "docs" / "demo-runbook.md"
    ).read_text(encoding="utf-8")
    for term in (
        "local_files_only",
        "embedding_model_cache_missing",
        "embedding_model_cache_invalid",
        "--offline",
        "database_busy",
        "database_corrupt",
        "reset rollback",
        "CIVICPULSE_DB_PATH",
    ):
        assert term in text


def test_performance_report_is_concise_and_links_raw_json() -> None:
    root = Path(__file__).parents[2]
    text = (root / "docs" / "performance-report.md").read_text(encoding="utf-8")

    assert "benchmarks/reports/performance-budget.json" in text
    assert "p50" in text
    assert "p95" in text
    assert "Known noise sources" in text
    assert "No optimization was performed where the measured result already met budget." in text
