"""Deterministic extraction and tri-state comparison of explicit locations."""

from __future__ import annotations

import re
from collections.abc import Iterable

from civicpulse.domain import (
    LocationComparison,
    LocationCompatibility,
    LocationEntity,
    LocationEntityKind,
)
from civicpulse.normalize import normalize_text


_STOP_WORDS = {
    "after",
    "ada",
    "again",
    "at",
    "banjir",
    "blocked",
    "blinking",
    "blink",
    "crossing",
    "dekat",
    "dengan",
    "flood",
    "flooded",
    "hujan",
    "junction",
    "jalan",
    "keeps",
    "lagi",
    "malam",
    "mati",
    "near",
    "on",
    "parking",
    "area",
    "pothole",
    "road",
    "rosak",
    "school",
    "selepas",
    "tersumbat",
    "the",
    "tadi",
    "then",
    "zebra",
}
_LANDMARK_PREFIXES = (
    ("sekolah menengah kebangsaan", "school"),
    ("sekolah kebangsaan", "school"),
    ("sekolah", "school"),
    ("school", "school"),
    ("hospital", "hospital"),
    ("clinic", "clinic"),
    ("stesen", "station"),
    ("station", "station"),
    ("mall", "mall"),
    ("pasar", "market"),
    ("market", "market"),
    ("park", "park"),
    ("taman permainan", "park"),
)


def _tokens_after(text: str, start: int, *, limit: int = 4) -> list[str]:
    tokens = text[start:].split()
    result: list[str] = []
    for token in tokens:
        if token in _STOP_WORDS or len(result) >= limit:
            break
        result.append(token)
    return result


def _entity(kind: LocationEntityKind, value: str, raw: str) -> LocationEntity:
    return LocationEntity(kind=kind, value=value.strip(), raw=raw.strip())


def extract_location_entities(text: str) -> tuple[LocationEntity, ...]:
    """Extract only explicit, deterministic location mentions.

    Generic phrases such as ``near school`` intentionally produce no landmark
    entity because there is no named place to compare.
    """
    normalized = normalize_text(text)
    entities: list[LocationEntity] = []

    for match in re.finditer(r"\b(?:block|blok)(?:\s+|[-#]\s*)([a-z0-9]+)\b", normalized):
        entities.append(_entity(LocationEntityKind.BLOCK, match.group(1), match.group(0)))

    for match in re.finditer(r"\bunit\s*[-#]?\s*([a-z0-9]+)\b", normalized):
        entities.append(_entity(LocationEntityKind.UNIT, match.group(1), match.group(0)))

    street_pattern = r"\b(?:jalan|lorong|taman|kampung)\s+([a-z0-9]+(?:\s+[a-z0-9]+){0,2})"
    for match in re.finditer(street_pattern, normalized):
        name = " ".join(_tokens_after(match.group(1), 0, limit=3))
        if name:
            entities.append(_entity(LocationEntityKind.STREET, name, match.group(0)))

    landmark_pattern = "|".join(re.escape(prefix) for prefix, _ in _LANDMARK_PREFIXES)
    for match in re.finditer(rf"\b({landmark_pattern})\b", normalized):
        prefix = match.group(1)
        category = next(value for key, value in _LANDMARK_PREFIXES if key == prefix)
        name_tokens = _tokens_after(normalized, match.end(), limit=4)
        if name_tokens:
            entities.append(
                _entity(LocationEntityKind.LANDMARK, f"{category}:{' '.join(name_tokens)}", match.group(0))
            )

    unique: dict[tuple[LocationEntityKind, str], LocationEntity] = {}
    for entity in entities:
        unique[(entity.kind, entity.value)] = entity
    return tuple(unique.values())


def compare_location_entities(
    first: Iterable[LocationEntity], second: Iterable[LocationEntity]
) -> LocationComparison:
    first_entities = tuple(first)
    second_entities = tuple(second)
    first_by_kind: dict[LocationEntityKind, set[str]] = {}
    second_by_kind: dict[LocationEntityKind, set[str]] = {}
    for entity in first_entities:
        first_by_kind.setdefault(entity.kind, set()).add(entity.value)
    for entity in second_entities:
        second_by_kind.setdefault(entity.kind, set()).add(entity.value)

    shared_kinds = set(first_by_kind) & set(second_by_kind)
    for kind in sorted(shared_kinds, key=lambda value: value.value):
        if first_by_kind[kind].isdisjoint(second_by_kind[kind]):
            return LocationComparison(
                compatibility=LocationCompatibility.CONFLICTING,
                first_entities=first_entities,
                second_entities=second_entities,
                reasons=(f"conflicting {kind.value} entities",),
            )

    if not first_entities or not second_entities:
        return LocationComparison(
            compatibility=LocationCompatibility.UNKNOWN,
            first_entities=first_entities,
            second_entities=second_entities,
            reasons=("one or both complaints lack explicit comparable location entities",),
        )

    if shared_kinds:
        return LocationComparison(
            compatibility=LocationCompatibility.COMPATIBLE,
            first_entities=first_entities,
            second_entities=second_entities,
            reasons=("at least one explicit location entity agrees",),
        )

    return LocationComparison(
        compatibility=LocationCompatibility.UNKNOWN,
        first_entities=first_entities,
        second_entities=second_entities,
        reasons=("explicit entities exist but have no comparable kind",),
    )
