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
