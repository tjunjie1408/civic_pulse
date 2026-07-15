"""Production composition root for the local CivicPulse demo."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from civicpulse.api.app import AppSettings, create_app
from civicpulse.config import load_matching_policy, load_priority_policy
from civicpulse.domain import SensitiveLocation
from civicpulse.embeddings import (
    EmbeddingProvider,
    ModelCacheInvalid,
    SentenceTransformerProvider,
)
from civicpulse.incident_query import IncidentQueryService
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService, SeedManifest


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    database_path: Path = Path("data/civicpulse.db")
    matching_policy_path: Path = Path("config/matching_policy.json")
    priority_policy_path: Path = Path("config/priority_policy.json")
    seed_path: Path = Path("data/seed_complaints.json")
    sensitive_locations_path: Path = Path("data/sensitive_locations.json")
    admin_reset_enabled: bool = False

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> RuntimeSettings:
        source = os.environ if environ is None else environ
        raw_reset = source.get("CIVICPULSE_ADMIN_RESET_ENABLED", "false").casefold()
        if raw_reset not in {"true", "false", "1", "0"}:
            raise ValueError(
                "CIVICPULSE_ADMIN_RESET_ENABLED must be true, false, 1, or 0"
            )
        return cls(
            database_path=Path(source.get("CIVICPULSE_DB_PATH", "data/civicpulse.db")),
            matching_policy_path=Path(
                source.get("CIVICPULSE_MATCHING_POLICY_PATH", "config/matching_policy.json")
            ),
            priority_policy_path=Path(
                source.get("CIVICPULSE_PRIORITY_POLICY_PATH", "config/priority_policy.json")
            ),
            seed_path=Path(source.get("CIVICPULSE_SEED_PATH", "data/seed_complaints.json")),
            sensitive_locations_path=Path(
                source.get(
                    "CIVICPULSE_SENSITIVE_LOCATIONS_PATH",
                    "data/sensitive_locations.json",
                )
            ),
            admin_reset_enabled=raw_reset in {"true", "1"},
        )


_SENSITIVE_LOCATIONS = TypeAdapter(tuple[SensitiveLocation, ...])


def load_sensitive_locations(path: str | Path) -> tuple[SensitiveLocation, ...]:
    resolved = Path(path)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        locations = _SENSITIVE_LOCATIONS.validate_python(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid sensitive-location fixture: {resolved}") from exc
    if not locations:
        raise ValueError(f"sensitive-location fixture is empty: {resolved}")
    return locations


def load_seed_manifest(path: str | Path) -> SeedManifest:
    """Load only the validated manifest needed to compose a runtime."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        manifest = SeedManifest.model_validate(payload["manifest"])
    except (OSError, KeyError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("invalid seed manifest configuration") from exc
    return manifest


@dataclass(frozen=True, slots=True)
class RuntimeBundle:
    settings: RuntimeSettings
    repository: SQLiteRepository
    service: CivicPulseService
    incident_query_service: IncidentQueryService
    app: FastAPI
    startup_spans: dict[str, float] = field(default_factory=lambda: {})


def build_runtime(
    settings: RuntimeSettings | None = None,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> RuntimeBundle:
    composition_started = time.perf_counter()
    startup_spans: dict[str, float] = {}
    resolved = settings or RuntimeSettings.from_environment()
    matching_policy = load_matching_policy(resolved.matching_policy_path)
    priority_policy = load_priority_policy(resolved.priority_policy_path)
    sensitive_locations = load_sensitive_locations(resolved.sensitive_locations_path)
    seed_manifest = load_seed_manifest(resolved.seed_path)
    startup_spans["settings_and_policy_loading"] = time.perf_counter() - composition_started

    model_started = time.perf_counter()
    provider = embedding_provider or SentenceTransformerProvider.for_runtime(
        matching_policy.model_name,
        matching_policy.normalization_version,
        expected_dimension=seed_manifest.embedding_dimension,
    )
    startup_spans["model_provider_load"] = time.perf_counter() - model_started

    probe_started = time.perf_counter()
    probe = provider.embed(["CivicPulse offline model readiness check"])
    if len(probe) != 1 or len(probe[0]) != seed_manifest.embedding_dimension:
        raise ModelCacheInvalid("embedding_model_cache_invalid: readiness dimension mismatch")
    startup_spans["readiness_probe"] = time.perf_counter() - probe_started

    database_started = time.perf_counter()
    repository = SQLiteRepository(resolved.database_path)
    repository.initialize()
    service = CivicPulseService(
        repository,
        matching_policy,
        priority_policy,
        provider,
        sensitive_locations,
        embedding_verified=True,
    )
    if not repository.list_complaints():
        service.initialize_seed(resolved.seed_path)
    startup_spans["database_and_seed_initialization"] = time.perf_counter() - database_started

    app_started = time.perf_counter()
    incident_query_service = IncidentQueryService(
        repository,
        priority_policy,
        sensitive_locations,
    )
    app = create_app(
        AppSettings(
            admin_reset_enabled=resolved.admin_reset_enabled,
            seed_path=str(resolved.seed_path),
        ),
        service=service,
        repository=repository,
        health_service=service.health,
        incident_query_service=incident_query_service,
    )
    bundle = RuntimeBundle(
        settings=resolved,
        repository=repository,
        service=service,
        incident_query_service=incident_query_service,
        app=app,
        startup_spans={
            **startup_spans,
            "app_composition": time.perf_counter() - app_started,
            "runtime_composition_total": time.perf_counter() - composition_started,
        },
    )
    profile_path = os.environ.get("CIVICPULSE_STARTUP_PROFILE_PATH")
    if profile_path:
        Path(profile_path).write_text(
            json.dumps(bundle.startup_spans, sort_keys=True), encoding="utf-8"
        )
    return bundle


def create_runtime_app() -> FastAPI:
    return build_runtime().app
