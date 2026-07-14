import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from civicpulse.api.dto.complaints import ComplaintCreateRequest
from civicpulse.geo import haversine_metres
from civicpulse.runtime import RuntimeSettings, build_runtime, load_sensitive_locations


class FakeProvider:
    model_name = "intfloat/multilingual-e5-small"
    normalization_version = "normalization-v1"

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, *([0.0] * 383)) for _ in texts)


def runtime_settings(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        database_path=tmp_path / "civicpulse.db",
        seed_path=Path("data/seed_complaints.json"),
        sensitive_locations_path=Path("data/sensitive_locations.json"),
    )


def test_runtime_settings_read_server_owned_paths_and_safe_reset_flag(tmp_path: Path) -> None:
    settings = RuntimeSettings.from_environment(
        {
            "CIVICPULSE_DB_PATH": str(tmp_path / "demo.db"),
            "CIVICPULSE_SEED_PATH": "approved/seed.json",
            "CIVICPULSE_SENSITIVE_LOCATIONS_PATH": "approved/locations.json",
            "CIVICPULSE_ADMIN_RESET_ENABLED": "true",
        }
    )

    assert settings.database_path == tmp_path / "demo.db"
    assert settings.seed_path == Path("approved/seed.json")
    assert settings.sensitive_locations_path == Path("approved/locations.json")
    assert settings.admin_reset_enabled is True


def test_runtime_settings_reject_invalid_boolean() -> None:
    with pytest.raises(ValueError, match="CIVICPULSE_ADMIN_RESET_ENABLED"):
        RuntimeSettings.from_environment({"CIVICPULSE_ADMIN_RESET_ENABLED": "sometimes"})


def test_sensitive_location_loader_is_strict_and_names_the_path(tmp_path: Path) -> None:
    path = tmp_path / "locations.json"
    path.write_text(
        json.dumps([{"id": "school", "kind": "school", "latitude": 91, "longitude": 1}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"locations\.json"):
        load_sensitive_locations(path)


def test_runtime_composes_ready_api_from_empty_database(tmp_path: Path) -> None:
    runtime = build_runtime(runtime_settings(tmp_path), embedding_provider=FakeProvider())
    response = TestClient(runtime.app).get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["core_ready"] is True
    assert len(runtime.repository.list_complaints()) == 120
    assert runtime.app.state.service is runtime.service
    assert runtime.app.state.repository is runtime.repository
    assert runtime.app.state.incident_query_service is runtime.incident_query_service


def test_runtime_restart_preserves_non_empty_state(tmp_path: Path) -> None:
    settings = runtime_settings(tmp_path)
    first = build_runtime(settings, embedding_provider=FakeProvider())
    response = TestClient(first.app).post(
        "/api/v1/complaints",
        headers={"Idempotency-Key": "runtime-restart"},
        json=ComplaintCreateRequest(
            text="Blocked drain at Block A",
            category="blocked_drain",
            latitude=3.08011,
            longitude=101.51847,
            reported_at=datetime(2026, 7, 11, 8, tzinfo=UTC),
        ).model_dump(mode="json"),
    )
    assert response.status_code == 201

    restarted = build_runtime(settings, embedding_provider=FakeProvider())

    assert len(restarted.repository.list_complaints()) == 121


def test_demo_sensitive_locations_align_with_current_synthetic_seed() -> None:
    locations = load_sensitive_locations("data/sensitive_locations.json")
    school = next(item for item in locations if item.kind == "school")

    assert all(item.id.startswith("synthetic-") for item in locations)
    assert haversine_metres(
        school.latitude,
        school.longitude,
        3.08011,
        101.51847,
    ) <= 250
