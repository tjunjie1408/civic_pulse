"""Production composition root for the local CivicPulse demo."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from civicpulse.api.app import AppSettings, create_app
from civicpulse.config import load_matching_policy, load_priority_policy
from civicpulse.domain import SensitiveLocation
from civicpulse.embeddings import EmbeddingProvider, SentenceTransformerProvider
from civicpulse.incident_query import IncidentQueryService
from civicpulse.repository import SQLiteRepository
from civicpulse.service import CivicPulseService


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


@dataclass(frozen=True, slots=True)
class RuntimeBundle:
    settings: RuntimeSettings
    repository: SQLiteRepository
    service: CivicPulseService
    incident_query_service: IncidentQueryService
    app: FastAPI


def build_runtime(
    settings: RuntimeSettings | None = None,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> RuntimeBundle:
    resolved = settings or RuntimeSettings.from_environment()
    matching_policy = load_matching_policy(resolved.matching_policy_path)
    priority_policy = load_priority_policy(resolved.priority_policy_path)
    sensitive_locations = load_sensitive_locations(resolved.sensitive_locations_path)
    repository = SQLiteRepository(resolved.database_path)
    repository.initialize()
    provider = embedding_provider or SentenceTransformerProvider(
        matching_policy.model_name,
        matching_policy.normalization_version,
    )
    service = CivicPulseService(
        repository,
        matching_policy,
        priority_policy,
        provider,
        sensitive_locations,
    )
    if not repository.list_complaints():
        service.initialize_seed(resolved.seed_path)
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
    return RuntimeBundle(
        settings=resolved,
        repository=repository,
        service=service,
        incident_query_service=incident_query_service,
        app=app,
    )


def create_runtime_app() -> FastAPI:
    return build_runtime().app
