"""Readiness response contract."""

from __future__ import annotations

from civicpulse.api.dto.common import ApiModel, HealthComponentResponse
from civicpulse.service import HealthReport, HealthStatus


class HealthResponse(ApiModel):
    status: HealthStatus
    core_ready: bool
    database: HealthComponentResponse
    policies: HealthComponentResponse
    embedding_model: HealthComponentResponse
    seed: HealthComponentResponse
    photo_provider: HealthComponentResponse

    @classmethod
    def from_domain(cls, report: HealthReport) -> HealthResponse:
        return cls(
            status=report.status,
            core_ready=report.core_ready,
            database=HealthComponentResponse.model_validate(report.database.model_dump()),
            policies=HealthComponentResponse.model_validate(report.policies.model_dump()),
            embedding_model=HealthComponentResponse.model_validate(report.embedding_model.model_dump()),
            seed=HealthComponentResponse.model_validate(report.seed.model_dump()),
            photo_provider=HealthComponentResponse.model_validate(report.photo_provider.model_dump()),
        )
