"""Deterministic, conservative normalization for complaint text."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AliasConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["normalization-v1"]
    aliases: dict[str, str] = Field(min_length=1)


NORMALIZATION_VERSION = "normalization-v1"


@lru_cache(maxsize=1)
def _load_alias_config() -> AliasConfig:
    path = Path("config/normalization_aliases.json")
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        config: AliasConfig = AliasConfig.model_validate(payload)
        if config.version != NORMALIZATION_VERSION:
            raise ValueError(f"Expected {NORMALIZATION_VERSION}, got {config.version}")
        return config
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Unable to load normalization aliases from {path}: {exc}") from exc


def _punctuation_to_spaces(text: str) -> str:
    return "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in text
    )


def normalize_text(text: str) -> str:
    """Normalize spelling aliases without translating or inventing facts."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = _punctuation_to_spaces(normalized)
    normalized = " ".join(normalized.split())
    for source, target in sorted(
        _load_alias_config().aliases.items(), key=lambda item: len(item[0]), reverse=True
    ):
        pattern = rf"(?<!\w){re.escape(source)}(?!\w)"
        normalized = re.sub(pattern, target, normalized)
    return " ".join(normalized.split())
