"""Explainable category detection for normalized complaint text."""

from __future__ import annotations

import re

from civicpulse.domain import Category, StrictModel


class CategoryPrediction(StrictModel):
    category: Category
    matched_terms: tuple[str, ...]
    review_required: bool


CATEGORY_TERMS: dict[Category, tuple[str, ...]] = {
    Category.POTHOLE: ("pothole", "jalan berlubang", "lubang jalan", "road hole"),
    Category.BLOCKED_DRAIN: (
        "longkang tersumbat",
        "drain blocked",
        "blocked drain",
        "saliran tersumbat",
    ),
    Category.FLOODING: ("banjir", "flood", "flooding", "flooded", "air naik", "flash flood"),
    Category.RUBBISH: (
        "sampah tidak dikutip",
        "sampah tak kutip",
        "garbage",
        "rubbish",
        "overflowing bin",
    ),
    Category.STREET_LIGHT: ("lampu jalan", "street light", "streetlight", "lampu rosak"),
}


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def classify_category(normalized_text: str) -> CategoryPrediction:
    """Return one category only when a unique strongest signal exists."""
    matches: dict[Category, list[str]] = {
        category: [term for term in terms if _contains_term(normalized_text, term)]
        for category, terms in CATEGORY_TERMS.items()
    }
    scored = {
        category: terms
        for category, terms in matches.items()
        if terms
    }
    if not scored:
        return CategoryPrediction(category=Category.OTHER, matched_terms=(), review_required=True)

    highest = max(len(terms) for terms in scored.values())
    winners = [category for category, terms in scored.items() if len(terms) == highest]
    all_terms = tuple(sorted(term for terms in scored.values() for term in terms))
    if len(winners) != 1:
        return CategoryPrediction(
            category=Category.OTHER,
            matched_terms=all_terms,
            review_required=True,
        )

    return CategoryPrediction(
        category=winners[0],
        matched_terms=tuple(sorted(scored[winners[0]])),
        review_required=False,
    )
