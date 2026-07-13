import json
from datetime import datetime, timezone
from pathlib import Path

from civicpulse.config import load_matching_policy, load_priority_policy
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService, SeedComplaint


class FakeProvider:
    model_name = "intfloat/multilingual-e5-small"
    normalization_version = "normalization-v1"

    def embed(self, texts):
        return tuple((1.0, 0.0) for _ in texts)


class FailingProvider(FakeProvider):
    def embed(self, texts):
        raise RuntimeError("model unavailable")


def write_one_record_seed(path: Path) -> None:
    complaint = {
        "seed_key": "health-complaint",
        "text": "Pothole here",
        "latitude": 3.1390,
        "longitude": 101.6869,
        "reported_at": datetime(2026, 7, 10, 8, tzinfo=timezone.utc).isoformat(),
        "category": "pothole",
    }
    canonical = {
        "complaints": [SeedComplaint.model_validate(complaint).model_dump(mode="json")],
        "review_resolutions": [],
    }
    import hashlib

    content = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    payload = {
        "manifest": {
            "seed_version": "health-seed-v1",
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "normalization_version": "normalization-v1",
            "embedding_model": "intfloat/multilingual-e5-small",
            "embedding_dimension": 2,
            "matching_policy_version": "matching-v1",
            "priority_policy_version": "priority-v1",
        },
        **canonical,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_service(tmp_path: Path, provider=None, photo_healthcheck=None):
    repository = SQLiteRepository(tmp_path / "civicpulse.db")
    repository.initialize()
    return CivicPulseService(
        repository,
        load_matching_policy("config/matching_policy.json"),
        load_priority_policy("config/priority_policy.json"),
        provider or FakeProvider(),
        photo_healthcheck=photo_healthcheck,
    ), repository


def seed_service(tmp_path: Path):
    service, repository = make_service(tmp_path)
    seed = tmp_path / "seed.json"
    write_one_record_seed(seed)
    service.initialize_seed(seed)
    return service, repository


def test_health_is_unavailable_when_model_fails(tmp_path):
    service, repository = seed_service(tmp_path)
    service.embedding_provider = FailingProvider()

    report = service.health()

    assert report.core_ready is False
    assert report.status.value == "unavailable"
    assert report.embedding_model.status.value == "unavailable"
    assert report.embedding_model.recovery_command == (
        "uv run --offline python -m scripts.prewarm_model"
    )
    assert "sk-" not in report.embedding_model.message
    assert len(repository.list_complaints()) == 1


def test_health_is_unavailable_when_database_check_fails(tmp_path, monkeypatch):
    service, _ = seed_service(tmp_path)

    def fail_database():
        raise OSError("locked")

    monkeypatch.setattr(service.repository, "health_check", fail_database)
    report = service.health()

    assert report.core_ready is False
    assert report.database.status.value == "unavailable"


def test_photo_provider_degrades_without_blocking_core(tmp_path):
    service, _ = seed_service(tmp_path)
    service.photo_healthcheck = lambda: (_ for _ in ()).throw(RuntimeError("missing key"))

    report = service.health()

    assert report.core_ready is True
    assert report.status.value == "degraded"
    assert report.photo_provider.status.value == "degraded"


def test_policy_model_mismatch_is_unavailable(tmp_path):
    service, _ = seed_service(tmp_path)
    service.embedding_provider = FakeProvider()
    service.embedding_provider.model_name = "wrong-model"

    report = service.health()

    assert report.core_ready is False
    assert report.policies.status.value == "unavailable"


def test_prewarm_command_runs_fixed_sentence(monkeypatch, tmp_path):
    from scripts import prewarm_model

    class StubProvider:
        def __init__(self, model_name, normalization_version):
            self.model_name = model_name

        def embed(self, texts):
            assert texts == ["CivicPulse offline model readiness check"]
            return ((1.0, 0.0),)

    monkeypatch.setattr(prewarm_model, "SentenceTransformerProvider", StubProvider)
    assert prewarm_model.prewarm("config/matching_policy.json") == 0
