"""Shared API contracts with explicit units and strict unknown-field handling."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from civicpulse.service import HealthStatus

type JsonScalar = str | int | float | bool | None


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GeoPointResponse(ApiModel):
    latitude: float = Field(description="Latitude in decimal degrees.")
    longitude: float = Field(description="Longitude in decimal degrees.")


class ApiErrorBody(ApiModel):
    code: str
    message: str
    details: dict[str, JsonScalar]
    request_id: str


class ApiErrorResponse(ApiModel):
    error: ApiErrorBody


class LiveResponse(ApiModel):
    status: Literal["alive"] = "alive"


class HealthComponentResponse(ApiModel):
    status: HealthStatus
    message: str
    recovery_command: str | None = None
