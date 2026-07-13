"""Canonical OpenAPI generation without runtime service construction."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from civicpulse.api import create_app

CANONICALIZATION_VERSION = "1"
type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonDocument = Mapping[str, object]


def _mapping_key(parent: str | None, key: str) -> tuple[int, str]:
    if parent == "responses":
        if key.isdigit():
            return 0, f"{int(key):03d}"
        return 1, key
    return 0, key


def _list_key(parent: str | None, value: JsonValue) -> tuple[str, str]:
    if parent == "parameters" and isinstance(value, Mapping):
        return str(value.get("in", "")), str(value.get("name", value.get("$ref", "")))
    if parent == "tags":
        return "", str(value)
    return "", json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonicalize(value: JsonValue, parent: str | None = None) -> JsonValue:
    if isinstance(value, dict):
        return {
            key: _canonicalize(value[key], key)
            for key in sorted(value, key=lambda item: _mapping_key(parent, str(item)))
        }
    if isinstance(value, list):
        items = [_canonicalize(item, parent) for item in value]
        if parent in {"parameters", "tags"}:
            return sorted(items, key=lambda item: _list_key(parent, item))
        return items
    return value


def canonicalize_openapi(document: JsonDocument) -> dict[str, JsonValue]:
    """Return a deterministic copy while preserving every OpenAPI field."""
    result = _canonicalize(cast(JsonValue, dict(document)))
    if not isinstance(result, dict):
        raise TypeError("OpenAPI document must be a JSON object")
    return result


def canonical_json(document: JsonDocument) -> bytes:
    """Serialize a canonical OpenAPI document with stable UTF-8 formatting."""
    return (
        json.dumps(
            canonicalize_openapi(document),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def write_openapi_snapshot(output: str | Path) -> Path:
    """Write the generated canonical document to an explicitly supplied path."""
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical_json(create_app().openapi()))
    return destination
