"""Versioned, strictly validated runtime policy configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MatchingPolicy(PolicyModel):
    policy_version: str = Field(min_length=1)
    geographic_radius_metres: float = Field(gt=0, allow_inf_nan=False)
    temporal_window_days: float = Field(gt=0, allow_inf_nan=False)
    semantic_threshold: float = Field(ge=-1, le=1, allow_inf_nan=False)
    strong_entity_semantic_threshold: float = Field(ge=-1, le=1, allow_inf_nan=False)
    model_name: str = Field(min_length=1)
    normalization_version: str = Field(min_length=1)
    prototype_parameters: str = Field(min_length=1)


class VolumePointBand(PolicyModel):
    minimum_reports: int = Field(ge=1)
    points: int = Field(ge=1)


class PriorityBandThresholds(PolicyModel):
    low_max: int = Field(ge=0)
    medium: int = Field(ge=1)
    high: int = Field(ge=1)
    critical: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> "PriorityBandThresholds":
        if not self.low_max < self.medium < self.high < self.critical:
            raise ValueError("priority thresholds must be low_max < medium < high < critical")
        return self


class PriorityPolicy(PolicyModel):
    policy_version: str = Field(min_length=1)
    volume_points: tuple[VolumePointBand, ...] = Field(min_length=1)
    safety_signal_points: int = Field(ge=0)
    sensitive_location_points: int = Field(ge=0)
    unresolved_24h_points: int = Field(ge=0)
    unresolved_48h_points: int = Field(ge=0)
    photo_points: int = Field(ge=0)
    sensitive_location_radius_metres: float = Field(gt=0, allow_inf_nan=False)
    band_thresholds: PriorityBandThresholds
    prototype_parameters: str = Field(min_length=1)
    medium_report_count: int = Field(default=2, ge=1)
    high_report_count: int = Field(default=10, ge=1)
    critical_report_count: int = Field(default=20, ge=1)
    high_unresolved_hours: float = Field(default=24, gt=0, allow_inf_nan=False)
    critical_unresolved_hours: float = Field(default=48, gt=0, allow_inf_nan=False)
    evidence_completeness_threshold: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    critical_safety_signals: tuple[str, ...] = Field(
        default=("accident_injury", "exposed_electrical_hazard"), min_length=1
    )
    high_safety_signals: tuple[str, ...] = Field(
        default=("active_flooding", "blocked_road"), min_length=1
    )

    @model_validator(mode="after")
    def validate_operational_thresholds(self) -> "PriorityPolicy":
        if not self.medium_report_count < self.high_report_count < self.critical_report_count:
            raise ValueError(
                "report thresholds must be medium_report_count < high_report_count < critical_report_count"
            )
        if not self.high_unresolved_hours < self.critical_unresolved_hours:
            raise ValueError("unresolved hour thresholds must be high < critical")
        return self


PolicyType = TypeVar("PolicyType", MatchingPolicy, PriorityPolicy)


def _load(path: str | Path, model_type: type[PolicyType]) -> PolicyType:
    policy_path = Path(path)
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        return model_type.model_validate(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{policy_path}: unable to read valid JSON policy: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{policy_path}: invalid policy: {exc}") from exc


def load_matching_policy(path: str | Path) -> MatchingPolicy:
    return _load(path, MatchingPolicy)


def load_priority_policy(path: str | Path) -> PriorityPolicy:
    return _load(path, PriorityPolicy)
